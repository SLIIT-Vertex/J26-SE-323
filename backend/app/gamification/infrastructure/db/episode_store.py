"""SQLAlchemy unit of work for one adaptive episode."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.gamification.application.episode_state import EpisodeState, SupportExposureRecord
from app.gamification.application.errors import EpisodeFlowError
from app.gamification.application.records import (
    IndependenceOutcomeEvidence,
    ItemResponseEvidence,
    LearnerSkillSummary,
    SupportExposureEvidence,
    VerificationPairEvidence,
)
from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.types import (
    ActionId,
    DecisionMode,
    EpisodeId,
    EpisodePhase,
    FeatureSnapshotId,
    ItemId,
    PolicyDecisionId,
    ProtocolVersion,
    SkillId,
)
from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    GameSessionModel,
    IndependenceOutcomeModel,
    ItemResponseModel,
    LearnerSkillSummaryModel,
    MisconceptionInferenceModel,
    MisconceptionProbabilityModel,
    ModelVersionModel,
    SupportDecisionModel,
    SupportExposureModel,
    VerificationPairModel,
)
from app.gamification.infrastructure.db.repositories import (
    SqlAlchemyFeatureSnapshotStore,
    SqlAlchemyPolicyDecisionStore,
)
from app.gamification.infrastructure.memory import InMemoryAuditOutput
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

_MODEL_NAMESPACE = UUID("91c0b7e2-4a55-4d1e-8f33-0c6a9b2d4e70")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _score(value: float) -> Decimal:
    return Decimal("1.0000") if value >= 1 else Decimal("0.0000")


def _trigger_json(state: EpisodeState) -> dict[str, object] | None:
    if state.trigger_config_version is None:
        return None
    return {
        "reasons": list(state.trigger_reasons),
        "missing_inputs": list(state.trigger_missing_inputs),
        "skipped_rules": list(state.trigger_skipped_rules),
        "config_version": state.trigger_config_version,
    }


class SqlAlchemyLearningRecordStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_skill_summary(
        self, *, learner_id: UUID, skill_id: SkillId
    ) -> LearnerSkillSummary | None:
        row = self._session.get(LearnerSkillSummaryModel, (learner_id, str(skill_id)))
        if row is None:
            return None
        return _summary_from_row(row)

    def get(self, *, learner_id: UUID, skill_id: str) -> LearnerSkillSummary | None:
        return self.get_skill_summary(learner_id=learner_id, skill_id=SkillId(skill_id))

    def save(self, summary: LearnerSkillSummary) -> None:
        row = self._session.get(
            LearnerSkillSummaryModel, (summary.learner_id, summary.skill_id)
        )
        values = _summary_values(summary)
        if row is None:
            self._session.add(LearnerSkillSummaryModel(**values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        self._session.flush()

    def record_attempt(self, attempt: object) -> None:
        del attempt

    def seen_item_ids(self, *, learner_id: UUID) -> tuple[ItemId, ...]:
        rows = self._session.scalars(
            select(ItemResponseModel.item_id).where(ItemResponseModel.learner_id == learner_id)
        ).all()
        seen: list[ItemId] = []
        for item_id in rows:
            typed = ItemId(item_id)
            if typed not in seen:
                seen.append(typed)
        return tuple(seen)


class SqlAlchemyEpisodeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, state: EpisodeState) -> None:
        if self._session.get(AdaptiveEpisodeModel, state.episode.episode_id) is not None:
            raise EpisodeFlowError("EPISODE_ALREADY_OPEN")
        self._persist_children(state)
        self._session.add(self._episode_row(state))
        self._session.flush()

    def get(self, episode_id: EpisodeId) -> EpisodeState:
        self._session.expire_all()
        row = self._session.get(AdaptiveEpisodeModel, episode_id)
        if row is None:
            raise LookupError(str(episode_id))
        return self._to_state(row)

    def save(self, state: EpisodeState) -> EpisodeState:
        self._persist_children(state)
        values = self._episode_values(state)
        values["revision"] = state.revision + 1
        result = self._session.execute(
            update(AdaptiveEpisodeModel)
            .where(
                AdaptiveEpisodeModel.id == state.episode.episode_id,
                AdaptiveEpisodeModel.revision == state.revision,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise EpisodeFlowError("EPISODE_STATE_CONFLICT")
        self._session.flush()
        return self.get(state.episode.episode_id)

    def _persist_children(self, state: EpisodeState) -> None:
        self._write_responses(state)
        self._write_snapshot(state)
        self._write_inference(state)
        self._write_decision(state)
        self._write_exposures(state)
        self._write_pair(state)
        self._write_outcome(state)

    def _write_responses(self, state: EpisodeState) -> None:
        pending = [
            response
            for response in (
                state.baseline_response,
                *state.supported_responses,
                state.verification_response,
            )
            if response is not None
            and self._session.get(ItemResponseModel, response.response_id) is None
        ]
        supported_seen = 0
        for response in pending:
            hint_count = 0
            response_time_ms = None
            if (
                state.baseline_response
                and response.response_id == state.baseline_response.response_id
            ):
                hint_count = 1 if state.learner_requested_help else 0
                response_time_ms = state.baseline_response_time_ms
                role = "baseline"
                attempt_no = 1
            elif (
                state.verification_response
                and response.response_id == state.verification_response.response_id
            ):
                role = "verification"
                attempt_no = 1
            else:
                supported_seen += 1
                role = f"supported:{response.response_id}"
                attempt_no = supported_seen
            self._session.add(
                ItemResponseModel(
                    id=response.response_id,
                    session_id=state.session_id,
                    learner_id=state.episode.learner_id,
                    item_id=response.item_id,
                    item_version=response.item_version,
                    skill_code=state.episode.skill_id,
                    skill_taxonomy_version=state.taxonomy_version,
                    attempt_no=attempt_no,
                    phase=response.phase,
                    support_state=response.support_state,
                    answer_json=dict(response.answer),
                    is_correct=response.is_correct,
                    score=_score(response.score),
                    response_time_ms=response_time_ms,
                    hint_count=hint_count,
                    idempotency_key=f"{state.episode.episode_id}:{role}",
                    submitted_at=response.submitted_at,
                    created_at=response.submitted_at,
                )
            )
        if pending:
            self._session.flush()

    def _write_snapshot(self, state: EpisodeState) -> None:
        store = SqlAlchemyFeatureSnapshotStore(self._session)
        for snapshot in (state.feature_snapshot, state.policy_context_snapshot):
            if snapshot is not None and store.get(snapshot.snapshot_id) is None:
                store.add(snapshot)

    def _write_inference(self, state: EpisodeState) -> None:
        belief = state.belief
        snapshot = state.feature_snapshot
        if belief is None or snapshot is None:
            return
        existing = self._session.scalar(
            select(MisconceptionInferenceModel.id).where(
                MisconceptionInferenceModel.episode_id == state.episode.episode_id
            )
        )
        if existing is not None:
            return
        ordered = sorted(belief.probabilities.items(), key=lambda item: (-item[1], item[0]))
        inference_id = uuid5(_MODEL_NAMESPACE, f"{state.episode.episode_id}:inference")
        self._session.add(
            MisconceptionInferenceModel(
                id=inference_id,
                episode_id=state.episode.episode_id,
                model_version_id=self._ensure_model_version(belief.model_version),
                feature_snapshot_id=snapshot.snapshot_id,
                misconception_catalogue_version=belief.catalogue_version,
                top_misconception_code=ordered[0][0],
                entropy=belief.entropy,
                confidence=belief.confidence,
                abstained=belief.abstained,
                reason_codes_json=list(belief.reason_codes),
                inferred_at=snapshot.captured_at,
            )
        )
        for rank, (code, probability) in enumerate(ordered, start=1):
            self._session.add(
                MisconceptionProbabilityModel(
                    inference_id=inference_id,
                    misconception_code=code,
                    probability=probability,
                    rank=rank,
                )
            )
        self._session.flush()

    def _ensure_model_version(self, semantic_version: str) -> UUID:
        existing = self._session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.model_name == "misconception",
                ModelVersionModel.semantic_version == semantic_version,
            )
        )
        if existing is not None:
            return existing.id
        model_id = uuid5(_MODEL_NAMESPACE, semantic_version)
        self._session.add(
            ModelVersionModel(
                id=model_id,
                model_name="misconception",
                model_role="misconception",
                semantic_version=semantic_version,
                artifact_uri=f"memory://{semantic_version}",
                artifact_sha256=hashlib.sha256(semantic_version.encode()).hexdigest(),
                feature_definition_version="gamification-features-v2",
                training_dataset_id=None,
                metrics_json={"status": "engineering_draft"},
                approval_status="draft",
            )
        )
        self._session.flush()
        return model_id

    def _write_decision(self, state: EpisodeState) -> None:
        decision = state.decision
        if decision is None:
            return
        store = SqlAlchemyPolicyDecisionStore(self._session)
        if store.get(decision.decision_id) is None:
            store.add(decision)

    def _write_exposures(self, state: EpisodeState) -> None:
        if state.decision is None:
            return
        for record in state.exposures:
            if self._session.get(SupportExposureModel, record.evidence.exposure_id) is not None:
                continue
            self._session.add(
                SupportExposureModel(
                    id=record.evidence.exposure_id,
                    decision_id=state.decision.decision_id,
                    action_id=record.evidence.action_id,
                    presented_at=record.evidence.presented_at,
                    first_interaction_at=(
                        record.evidence.presented_at if record.interaction_count else None
                    ),
                    completed_at=record.evidence.completed_at,
                    duration_ms=record.evidence.duration_ms,
                    interaction_count=record.interaction_count,
                    delivery_status=record.evidence.delivery_status,
                    render_version=record.evidence.render_version,
                    maximum_duration_ms=record.maximum_duration_ms,
                    maximum_number_of_steps=record.maximum_number_of_steps,
                )
            )
        self._session.flush()

    def _write_pair(self, state: EpisodeState) -> None:
        pair = state.verification_pair
        if pair is None:
            return
        existing = self._session.scalar(
            select(VerificationPairModel.id).where(
                VerificationPairModel.episode_id == state.episode.episode_id
            )
        )
        if existing is not None:
            return
        self._session.add(
            VerificationPairModel(
                id=pair.pair_id,
                episode_id=state.episode.episode_id,
                baseline_item_id=pair.baseline_item_id,
                baseline_item_version=pair.baseline_item_version,
                verification_item_id=pair.verification_item_id,
                verification_item_version=pair.verification_item_version,
                skill_code=state.episode.skill_id,
                equivalence_version=pair.equivalence_version,
                difficulty_delta=0.0,
                surface_similarity=1.0,
                answer_overlap=pair.answer_overlap,
                review_status=pair.review_status,
            )
        )
        self._session.flush()

    def _write_outcome(self, state: EpisodeState) -> None:
        outcome = state.outcome
        pair = state.verification_pair
        if outcome is None or pair is None:
            return
        existing = self._session.scalar(
            select(IndependenceOutcomeModel.id).where(
                IndependenceOutcomeModel.episode_id == state.episode.episode_id
            )
        )
        if existing is not None:
            return
        self._session.add(
            IndependenceOutcomeModel(
                id=outcome.outcome_id,
                episode_id=state.episode.episode_id,
                verification_pair_id=pair.pair_id,
                baseline_score=_score(outcome.baseline_score),
                verification_score=_score(outcome.verification_score),
                raw_independence_gain=outcome.raw_independence_gain,
                validity=outcome.validity,
                baseline_support_state="unsupported",
                verification_support_state="unsupported",
                invalid_reason=outcome.invalid_reason,
                formula_version=outcome.formula_version,
                calculated_at=outcome.calculated_at,
            )
        )
        self._session.flush()

    def _episode_values(self, state: EpisodeState) -> dict[str, object]:
        episode = state.episode
        return {
            "phase": episode.phase.value,
            "trigger_type": state.trigger_type,
            "trigger_reasons_json": _trigger_json(state),
            "baseline_template": state.baseline_template,
            "baseline_response_id": (
                state.baseline_response.response_id if state.baseline_response else None
            ),
            "verification_response_id": (
                state.verification_response.response_id if state.verification_response else None
            ),
            "transitioned_at": episode.transitioned_at,
            "support_withdrawn_at": state.withdrawn_at,
            "closed_at": state.closed_at,
            "terminal_reason": episode.terminal_reason,
        }

    def _episode_row(self, state: EpisodeState) -> AdaptiveEpisodeModel:
        episode = state.episode
        return AdaptiveEpisodeModel(
            id=episode.episode_id,
            session_id=state.session_id,
            learner_id=episode.learner_id,
            skill_code=episode.skill_id,
            skill_taxonomy_version=state.taxonomy_version,
            episode_protocol_version=episode.protocol_version,
            opened_at=episode.created_at,
            revision=state.revision,
            created_at=episode.created_at,
            **self._episode_values(state),
        )

    def _to_state(self, row: AdaptiveEpisodeModel) -> EpisodeState:
        baseline = self._response(row.baseline_response_id)
        verification = self._response(row.verification_response_id)
        inference = self._session.scalar(
            select(MisconceptionInferenceModel).where(
                MisconceptionInferenceModel.episode_id == row.id
            )
        )
        snapshot = None
        belief = None
        if inference is not None:
            snapshot = SqlAlchemyFeatureSnapshotStore(self._session).get(
                FeatureSnapshotId(inference.feature_snapshot_id)
            )
            belief = self._belief(inference)
        decision_row = self._session.scalar(
            select(SupportDecisionModel).where(SupportDecisionModel.episode_id == row.id)
        )
        decision = None
        policy_context = None
        exposures: tuple[SupportExposureRecord, ...] = ()
        if decision_row is not None:
            decision = SqlAlchemyPolicyDecisionStore(self._session).get(
                PolicyDecisionId(decision_row.id)
            )
            exposures = self._exposures(decision_row.id)
            if (
                decision is not None
                and snapshot is not None
                and decision.feature_snapshot_id != snapshot.snapshot_id
            ):
                policy_context = SqlAlchemyFeatureSnapshotStore(self._session).get(
                    decision.feature_snapshot_id
                )
        payload = row.trigger_reasons_json or {}
        game_session = self._session.get(GameSessionModel, row.session_id)
        baseline_row = (
            self._session.get(ItemResponseModel, row.baseline_response_id)
            if row.baseline_response_id
            else None
        )
        return EpisodeState(
            episode=AdaptiveEpisode(
                episode_id=EpisodeId(row.id),
                learner_id=row.learner_id,
                skill_id=SkillId(row.skill_code),
                protocol_version=ProtocolVersion(row.episode_protocol_version),
                phase=EpisodePhase(row.phase),
                created_at=_aware(row.opened_at),
                transitioned_at=_aware(row.transitioned_at),
                terminal_reason=row.terminal_reason,
            ),
            session_id=row.session_id,
            taxonomy_version=row.skill_taxonomy_version,
            language=game_session.language if game_session is not None else "si",
            trigger_type=row.trigger_type,
            trigger_reasons=tuple(payload.get("reasons", ())),
            trigger_missing_inputs=tuple(payload.get("missing_inputs", ())),
            trigger_skipped_rules=tuple(payload.get("skipped_rules", ())),
            trigger_config_version=payload.get("config_version"),
            baseline_template=row.baseline_template,
            baseline_response=baseline,
            baseline_response_time_ms=(
                baseline_row.response_time_ms if baseline_row is not None else None
            ),
            learner_requested_help=(
                bool(baseline_row.hint_count) if baseline_row is not None else None
            ),
            verification_response=verification,
            supported_responses=self._supported_responses(row),
            feature_snapshot=snapshot,
            policy_context_snapshot=policy_context,
            belief=belief,
            decision=decision,
            exposures=exposures,
            withdrawn_at=_aware(row.support_withdrawn_at) if row.support_withdrawn_at else None,
            verification_pair=self._pair(row.id),
            outcome=self._outcome(row.id),
            decision_mode=(
                decision.mode if decision is not None else DecisionMode.DETERMINISTIC_REFERENCE
            ),
            revision=row.revision,
            closed_at=_aware(row.closed_at) if row.closed_at else None,
        )

    def _response(self, response_id: UUID | None) -> ItemResponseEvidence | None:
        if response_id is None:
            return None
        row = self._session.get(ItemResponseModel, response_id)
        if row is None:
            return None
        return _response_evidence(row)

    def _supported_responses(
        self, episode: AdaptiveEpisodeModel
    ) -> tuple[ItemResponseEvidence, ...]:
        rows = self._session.scalars(
            select(ItemResponseModel)
            .where(
                ItemResponseModel.session_id == episode.session_id,
                ItemResponseModel.phase == "supported",
                ItemResponseModel.idempotency_key.like(f"{episode.id}:supported:%"),
            )
            .order_by(ItemResponseModel.submitted_at)
        ).all()
        return tuple(_response_evidence(row) for row in rows)

    def _belief(self, inference: MisconceptionInferenceModel) -> MisconceptionDistribution:
        rows = self._session.scalars(
            select(MisconceptionProbabilityModel)
            .where(MisconceptionProbabilityModel.inference_id == inference.id)
            .order_by(MisconceptionProbabilityModel.rank)
        ).all()
        probabilities = {row.misconception_code: float(row.probability) for row in rows}
        total = sum(probabilities.values())
        if probabilities and abs(total - 1.0) > 1e-9:
            probabilities = {code: value / total for code, value in probabilities.items()}
        model = self._session.get(ModelVersionModel, inference.model_version_id)
        return MisconceptionDistribution(
            probabilities=probabilities,
            entropy=inference.entropy,
            confidence=inference.confidence,
            abstained=inference.abstained,
            model_version=model.semantic_version if model is not None else "",
            catalogue_version=inference.misconception_catalogue_version,
            reason_codes=tuple(inference.reason_codes_json),
        )

    def _exposures(self, decision_id: UUID) -> tuple[SupportExposureRecord, ...]:
        rows = self._session.scalars(
            select(SupportExposureModel)
            .where(SupportExposureModel.decision_id == decision_id)
            .order_by(SupportExposureModel.presented_at, SupportExposureModel.id)
        ).all()
        return tuple(
            SupportExposureRecord(
                evidence=SupportExposureEvidence(
                    exposure_id=row.id,
                    action_id=ActionId(row.action_id),
                    delivery_status=row.delivery_status,
                    presented_at=_aware(row.presented_at) if row.presented_at else None,
                    completed_at=_aware(row.completed_at) if row.completed_at else None,
                    duration_ms=row.duration_ms,
                    render_version=row.render_version,
                    maximum_duration_ms=row.maximum_duration_ms,
                    maximum_number_of_steps=row.maximum_number_of_steps,
                ),
                maximum_duration_ms=row.maximum_duration_ms or 0,
                maximum_number_of_steps=row.maximum_number_of_steps or 0,
                interaction_count=row.interaction_count,
            )
            for row in rows
        )

    def _pair(self, episode_id: UUID) -> VerificationPairEvidence | None:
        row = self._session.scalar(
            select(VerificationPairModel).where(VerificationPairModel.episode_id == episode_id)
        )
        if row is None:
            return None
        return VerificationPairEvidence(
            pair_id=row.id,
            baseline_item_id=ItemId(row.baseline_item_id),
            baseline_item_version=row.baseline_item_version,
            verification_item_id=ItemId(row.verification_item_id),
            verification_item_version=row.verification_item_version,
            equivalence_version=row.equivalence_version,
            review_status=row.review_status,
            unseen_verification_item=True,
            answer_overlap=float(row.answer_overlap),
        )

    def _outcome(self, episode_id: UUID) -> IndependenceOutcomeEvidence | None:
        row = self._session.scalar(
            select(IndependenceOutcomeModel).where(
                IndependenceOutcomeModel.episode_id == episode_id
            )
        )
        if row is None:
            return None
        return IndependenceOutcomeEvidence(
            outcome_id=row.id,
            validity=row.validity,
            baseline_score=float(row.baseline_score),
            verification_score=float(row.verification_score),
            raw_independence_gain=(
                float(row.raw_independence_gain) if row.raw_independence_gain is not None else None
            ),
            invalid_reason=row.invalid_reason,
            formula_version=row.formula_version,
            calculated_at=_aware(row.calculated_at),
        )


def _response_evidence(row: ItemResponseModel) -> ItemResponseEvidence:
    return ItemResponseEvidence(
        response_id=row.id,
        item_id=ItemId(row.item_id),
        item_version=row.item_version,
        phase=row.phase,
        support_state=row.support_state,
        answer=row.answer_json,
        is_correct=row.is_correct,
        score=float(row.score),
        submitted_at=_aware(row.submitted_at),
    )


class SqlAlchemyUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.episodes = SqlAlchemyEpisodeRepository(session)
        self.learning_records = SqlAlchemyLearningRecordStore(session)
        self.audit = InMemoryAuditOutput()
        self._audit_mark = 0

    def begin(self) -> None:
        self._audit_mark = len(self.audit.events)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
        del self.audit.events[self._audit_mark :]


def _summary_values(summary: LearnerSkillSummary) -> dict[str, object]:
    return {
        "learner_id": summary.learner_id,
        "skill_code": summary.skill_id,
        "unsupported_attempts": summary.unsupported_attempts,
        "supported_attempts": summary.supported_attempts,
        "independent_accuracy": summary.independent_accuracy,
        "supported_accuracy": summary.supported_accuracy,
        "mean_independence_gain": summary.mean_independence_gain,
        "support_dependency_index": summary.support_dependency_index,
        "valid_outcome_count": summary.valid_outcome_count,
        "last_practiced_at": summary.last_practiced_at,
        "summary_version": summary.summary_version,
        "updated_at": summary.updated_at,
    }


def _summary_from_row(row: LearnerSkillSummaryModel) -> LearnerSkillSummary:
    return LearnerSkillSummary(
        learner_id=row.learner_id,
        skill_id=row.skill_code,
        unsupported_attempts=row.unsupported_attempts,
        supported_attempts=row.supported_attempts,
        independent_accuracy=row.independent_accuracy,
        supported_accuracy=row.supported_accuracy,
        mean_independence_gain=row.mean_independence_gain,
        support_dependency_index=row.support_dependency_index,
        valid_outcome_count=row.valid_outcome_count,
        last_practiced_at=_aware(row.last_practiced_at) if row.last_practiced_at else None,
        summary_version=row.summary_version,
        updated_at=_aware(row.updated_at),
    )
