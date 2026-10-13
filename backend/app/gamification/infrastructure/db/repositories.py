from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.application.records import (
    EpisodeEvidenceBundle,
    FeatureSnapshotRecord,
    IndependenceOutcomeEvidence,
    ItemResponseEvidence,
    MisconceptionBeliefEvidence,
    ModelArtifact,
    PolicyCandidateRecord,
    PolicyDecisionRecord,
    SupportExposureEvidence,
    VerificationPairEvidence,
)
from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    DecisionMode,
    EpisodeId,
    EpisodePhase,
    FeatureSnapshotId,
    ModelId,
    PolicyDecisionId,
    ProtocolVersion,
    SkillId,
    SupportActionType,
    TaxonomyVersion,
)
from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    FeatureSnapshotModel,
    IndependenceOutcomeModel,
    ItemResponseModel,
    MisconceptionInferenceModel,
    MisconceptionProbabilityModel,
    ModelVersionModel,
    SupportCandidateModel,
    SupportDecisionModel,
    SupportExposureModel,
    VerificationPairModel,
)


def _aware(value: datetime) -> datetime:
    """SQLite drops offsets; persisted timestamps are defined as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")


class SqlAlchemyFeatureSnapshotStore:
    """Append-only snapshot adapter; transaction ownership remains with the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, snapshot: FeatureSnapshotRecord) -> None:
        _require_aware(snapshot.captured_at, "captured_at")
        self._session.add(
            FeatureSnapshotModel(
                id=snapshot.snapshot_id,
                learner_id=snapshot.learner_id,
                skill_code=snapshot.skill_id,
                captured_at=snapshot.captured_at,
                protocol_version=snapshot.protocol_version,
                taxonomy_version=snapshot.taxonomy_version,
                definition_version=snapshot.feature_definition_version,
                purpose=snapshot.purpose,
                features_json=dict(snapshot.values),
                missingness_json=dict(snapshot.missingness),
                source_as_of_json=dict(snapshot.source_as_of),
            )
        )
        self._session.flush()

    def get(self, snapshot_id: FeatureSnapshotId) -> FeatureSnapshotRecord | None:
        row = self._session.get(FeatureSnapshotModel, snapshot_id)
        if row is None:
            return None
        return FeatureSnapshotRecord(
            snapshot_id=FeatureSnapshotId(row.id),
            learner_id=row.learner_id,
            skill_id=SkillId(row.skill_code),
            captured_at=_aware(row.captured_at),
            protocol_version=ProtocolVersion(row.protocol_version),
            taxonomy_version=TaxonomyVersion(row.taxonomy_version),
            feature_definition_version=row.definition_version,
            values=row.features_json,
            missingness=row.missingness_json,
            source_as_of=row.source_as_of_json,
            purpose=row.purpose,
        )


class SqlAlchemyPolicyDecisionStore:
    """Stores one immutable decision and its complete candidate set atomically on flush."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, decision: PolicyDecisionRecord) -> None:
        _require_aware(decision.decided_at, "decided_at")
        if not decision.candidates:
            raise ValueError("policy decision requires at least one candidate")
        eligible = [candidate for candidate in decision.candidates if candidate.eligible]
        if not eligible or abs(sum(candidate.propensity for candidate in eligible) - 1.0) > 1e-9:
            raise ValueError("eligible candidate propensities must sum to one")
        selected = next(
            (
                candidate
                for candidate in eligible
                if candidate.action_id == decision.selected_action_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("selected action must be eligible")

        self._session.add(
            SupportDecisionModel(
                id=decision.decision_id,
                episode_id=decision.episode_id,
                policy_model_version_id=None,
                feature_snapshot_id=decision.feature_snapshot_id,
                selected_action_id=decision.selected_action_id,
                selected_action_type=selected.action_type,
                selection_probability=selected.propensity,
                decision_mode=decision.mode,
                policy_version=decision.policy_version,
                support_catalogue_version=decision.support_catalogue_version,
                reason_codes_json=list(decision.reason_codes),
                random_seed=decision.random_seed,
                decided_at=decision.decided_at,
            )
        )
        for rank, candidate in enumerate(decision.candidates, start=1):
            self._session.add(
                SupportCandidateModel(
                    decision_id=decision.decision_id,
                    action_id=candidate.action_id,
                    action_type=candidate.action_type,
                    eligible=candidate.eligible,
                    ineligibility_reasons_json=(
                        [] if candidate.eligible else list(candidate.reason_codes)
                    ),
                    predicted_reward=candidate.predicted_reward,
                    uncertainty=candidate.uncertainty,
                    propensity=candidate.propensity,
                    rank=rank,
                )
            )
        self._session.flush()

    def get(self, decision_id: PolicyDecisionId) -> PolicyDecisionRecord | None:
        row = self._session.get(SupportDecisionModel, decision_id)
        if row is None:
            return None
        candidates = self._session.scalars(
            select(SupportCandidateModel)
            .where(SupportCandidateModel.decision_id == decision_id)
            .order_by(SupportCandidateModel.rank)
        ).all()
        return PolicyDecisionRecord(
            decision_id=PolicyDecisionId(row.id),
            episode_id=EpisodeId(row.episode_id),
            feature_snapshot_id=FeatureSnapshotId(row.feature_snapshot_id),
            selected_action_id=ActionId(row.selected_action_id),
            mode=DecisionMode(row.decision_mode),
            policy_version=row.policy_version,
            support_catalogue_version=CatalogueVersion(row.support_catalogue_version),
            candidates=tuple(
                PolicyCandidateRecord(
                    action_id=ActionId(candidate.action_id),
                    action_type=SupportActionType(candidate.action_type),
                    propensity=candidate.propensity,
                    eligible=candidate.eligible,
                    reason_codes=tuple(candidate.ineligibility_reasons_json),
                    predicted_reward=candidate.predicted_reward,
                    uncertainty=candidate.uncertainty,
                )
                for candidate in candidates
            ),
            reason_codes=tuple(row.reason_codes_json),
            decided_at=_aware(row.decided_at),
            random_seed=row.random_seed,
        )


class SqlAlchemyModelRegistry:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_approved(self, model_id: ModelId) -> ModelArtifact | None:
        row = self._session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.id == model_id,
                ModelVersionModel.approval_status == "approved",
            )
        )
        if row is None:
            return None
        return ModelArtifact(
            model_id=ModelId(row.id),
            model_version=row.semantic_version,
            artifact_digest=f"sha256:{row.artifact_sha256}",
            approved=True,
            registered_at=_aware(row.created_at),
        )


def reconstruct_episode_evidence(
    session: Session, episode_id: EpisodeId
) -> EpisodeEvidenceBundle:
    """Load immutable evidence without consulting current mastery, state, or summaries."""
    episode_row = session.get(AdaptiveEpisodeModel, episode_id)
    if episode_row is None:
        raise LookupError(f"adaptive episode does not exist: {episode_id}")

    def response_evidence(response_id: object | None) -> ItemResponseEvidence | None:
        if response_id is None:
            return None
        row = session.get(ItemResponseModel, response_id)
        if row is None:
            raise LookupError(f"episode references missing item response: {response_id}")
        return ItemResponseEvidence(
            response_id=row.id,
            item_id=row.item_id,
            item_version=row.item_version,
            phase=row.phase,
            support_state=row.support_state,
            answer=row.answer_json,
            is_correct=row.is_correct,
            score=float(row.score),
            submitted_at=_aware(row.submitted_at),
        )

    inference = session.scalar(
        select(MisconceptionInferenceModel).where(
            MisconceptionInferenceModel.episode_id == episode_id
        )
    )
    beliefs: tuple[MisconceptionBeliefEvidence, ...] = ()
    if inference is not None:
        probability_rows = session.scalars(
            select(MisconceptionProbabilityModel)
            .where(MisconceptionProbabilityModel.inference_id == inference.id)
            .order_by(MisconceptionProbabilityModel.rank)
        ).all()
        beliefs = tuple(
            MisconceptionBeliefEvidence(
                misconception_code=row.misconception_code,
                probability=row.probability,
                rank=row.rank,
            )
            for row in probability_rows
        )

    decision_row = session.scalar(
        select(SupportDecisionModel).where(SupportDecisionModel.episode_id == episode_id)
    )
    decision = None
    snapshot = None
    exposures: tuple[SupportExposureEvidence, ...] = ()
    if decision_row is not None:
        decision = SqlAlchemyPolicyDecisionStore(session).get(
            PolicyDecisionId(decision_row.id)
        )
        snapshot = SqlAlchemyFeatureSnapshotStore(session).get(
            FeatureSnapshotId(decision_row.feature_snapshot_id)
        )
        exposure_rows = session.scalars(
            select(SupportExposureModel)
            .where(SupportExposureModel.decision_id == decision_row.id)
            .order_by(SupportExposureModel.presented_at, SupportExposureModel.id)
        ).all()
        exposures = tuple(
            SupportExposureEvidence(
                exposure_id=row.id,
                action_id=ActionId(row.action_id),
                delivery_status=row.delivery_status,
                presented_at=_aware(row.presented_at) if row.presented_at else None,
                completed_at=_aware(row.completed_at) if row.completed_at else None,
                duration_ms=row.duration_ms,
                render_version=row.render_version,
            )
            for row in exposure_rows
        )

    pair_row = session.scalar(
        select(VerificationPairModel).where(VerificationPairModel.episode_id == episode_id)
    )
    pair = (
        VerificationPairEvidence(
            pair_id=pair_row.id,
            baseline_item_id=pair_row.baseline_item_id,
            baseline_item_version=pair_row.baseline_item_version,
            verification_item_id=pair_row.verification_item_id,
            verification_item_version=pair_row.verification_item_version,
            equivalence_version=pair_row.equivalence_version,
            review_status=pair_row.review_status,
        )
        if pair_row is not None
        else None
    )
    outcome_row = session.scalar(
        select(IndependenceOutcomeModel).where(
            IndependenceOutcomeModel.episode_id == episode_id
        )
    )
    outcome = (
        IndependenceOutcomeEvidence(
            outcome_id=outcome_row.id,
            validity=outcome_row.validity,
            baseline_score=float(outcome_row.baseline_score),
            verification_score=float(outcome_row.verification_score),
            raw_independence_gain=(
                float(outcome_row.raw_independence_gain)
                if outcome_row.raw_independence_gain is not None
                else None
            ),
            invalid_reason=outcome_row.invalid_reason,
            formula_version=outcome_row.formula_version,
            calculated_at=_aware(outcome_row.calculated_at),
        )
        if outcome_row is not None
        else None
    )
    return EpisodeEvidenceBundle(
        episode=AdaptiveEpisode(
            episode_id=EpisodeId(episode_row.id),
            learner_id=episode_row.learner_id,
            skill_id=SkillId(episode_row.skill_code),
            protocol_version=ProtocolVersion(episode_row.episode_protocol_version),
            phase=EpisodePhase(episode_row.phase),
            created_at=_aware(episode_row.opened_at),
            transitioned_at=_aware(episode_row.transitioned_at),
            terminal_reason=episode_row.terminal_reason,
        ),
        baseline_response=response_evidence(episode_row.baseline_response_id),
        verification_response=response_evidence(episode_row.verification_response_id),
        feature_snapshot=snapshot,
        misconception_beliefs=beliefs,
        policy_decision=decision,
        support_exposures=exposures,
        verification_pair=pair,
        outcome=outcome,
    )

