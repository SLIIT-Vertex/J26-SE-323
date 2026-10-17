"""Framework-free episode commands. Each command commits through a UnitOfWork."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from app.gamification.application.consent_gate import research_consent_granted
from app.gamification.application.episode_state import EpisodeState, SupportExposureRecord
from app.gamification.application.errors import EpisodeFlowError
from app.gamification.application.ports import (
    AuditOutput,
    ConsentStore,
    LearnerEvidencePublisher,
    LearnerStateGateway,
    LearningRecordStore,
    MasteryEvidenceGateway,
    SkillSummaryStore,
    UnitOfWork,
)
from app.gamification.application.records import (
    AuditEvent,
    FeatureSnapshotRecord,
    GamificationAttempt,
    IndependenceOutcomeEvidence,
    ItemResponseEvidence,
    LearnerEvidenceEvent,
    SupportExposureEvidence,
    VerificationPairEvidence,
)
from app.gamification.application.scaffold_controller import (
    ScaffoldController,
    answer_overlap,
    exposure_counts_as_completed,
)
from app.gamification.application.skill_summary import UpdateLearnerSkillSummary
from app.gamification.application.struggle_trigger import StruggleEvidence, StruggleTrigger
from app.gamification.application.template_selection import (
    TemplateCompatibilityTable,
    require_same_template,
)
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.records import ContentStatus, ItemDefinition
from app.gamification.domain.episode import ADAPTIVE_EPISODE_PROTOCOL, AdaptiveEpisode
from app.gamification.domain.types import (
    ActionId,
    ContractVersion,
    DecisionMode,
    EpisodeId,
    EpisodePhase,
    EvidenceSupportState,
    FeatureSnapshotId,
    ItemId,
    OutcomeValidity,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)
from app.gamification.modeling.independence_gain.contracts import (
    EquivalenceEvidence,
    IndependenceGainCalculator,
    IndependenceGainInput,
)
from app.gamification.modeling.independence_gain.resolution import misconception_resolution
from app.gamification.modeling.misconception_inference.contracts import MisconceptionPredictor
from app.gamification.modeling.shared.feature_building import (
    FEATURE_DEFINITION_VERSION,
    DecisionFeatureInput,
    FeatureBuilder,
)
from app.gamification.modeling.support_selection.context import (
    BanditContextBuilder,
    FixedMasteryGateway,
    QuestionContext,
    SupportHistory,
    policy_context_snapshot,
)
from app.gamification.modeling.support_selection.contracts import SupportSelector

_NAMESPACE = UUID("6f0e0c3a-7b1d-4e5f-9a2c-1d8e4b7c0a11")
_ATTEMPT_CONTRACT = ContractVersion("gamification-attempt-v1")
_FEATURE_PROTOCOL = "gamification-decision-v1"


def _difficulty_band(value: int) -> str:
    """Versioned mapping for the pilot's documented 1..3 numeric scale."""
    if value <= 1:
        return "easy"
    if value == 2:
        return "medium"
    return "hard"


@dataclass(frozen=True, slots=True)
class OpenAdaptiveEpisodeCommand:
    episode_id: EpisodeId
    session_id: UUID
    learner_id: UUID
    skill_id: SkillId
    taxonomy_version: str
    item_id: str
    selected_option_id: str
    submitted_at: datetime
    device_capabilities: frozenset[str]
    variation_seed: int
    response_time_ms: int | None = None
    incorrect_attempt_count: int | None = None
    learner_requested_help: bool | None = None
    language: str = "si"
    decision_mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE


@dataclass(frozen=True, slots=True)
class AssessStruggleCommand:
    episode_id: EpisodeId
    evidence: StruggleEvidence
    at: datetime


@dataclass(frozen=True, slots=True)
class InferMisconceptionBeliefsCommand:
    episode_id: EpisodeId
    at: datetime
    attempt_count: int
    recent_correctness: tuple[bool, ...] = ()
    source_as_of: Mapping[str, datetime] = field(default_factory=dict)
    mastery_probability: float | None = None
    mastery_uncertainty: float | None = None
    learner_support_need: float | None = None
    learner_state_reliability: float | None = None


@dataclass(frozen=True, slots=True)
class SelectSupportActionCommand:
    episode_id: EpisodeId
    at: datetime
    seed: int
    mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE


@dataclass(frozen=True, slots=True)
class RecordSupportExposureCommand:
    episode_id: EpisodeId
    at: datetime
    duration_ms: int
    step_count: int
    supported_item_id: str | None = None
    supported_option_id: str | None = None


@dataclass(frozen=True, slots=True)
class WithdrawSupportCommand:
    episode_id: EpisodeId
    at: datetime


@dataclass(frozen=True, slots=True)
class ScheduleUnsupportedVerificationCommand:
    episode_id: EpisodeId
    at: datetime


@dataclass(frozen=True, slots=True)
class RecordVerificationResponseCommand:
    episode_id: EpisodeId
    at: datetime
    selected_option_id: str
    response_time_ms: int | None = None


@dataclass(frozen=True, slots=True)
class CalculateIndependenceOutcomeCommand:
    episode_id: EpisodeId
    at: datetime
    idle_time_ms: int = 0
    maximum_idle_time_ms: int = 60_000


class EpisodeRepository:
    """Structural store implemented by the in-memory and SQLAlchemy adapters."""

    def insert(self, state: EpisodeState) -> None:
        raise NotImplementedError

    def get(self, episode_id: EpisodeId) -> EpisodeState:
        raise NotImplementedError

    def save(self, state: EpisodeState) -> EpisodeState:
        raise NotImplementedError


def run_unit[T](uow: UnitOfWork, work: Callable[[], T]) -> T:
    uow.begin()
    try:
        result = work()
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    return result


def _child_id(episode_id: EpisodeId, role: str) -> UUID:
    return uuid5(_NAMESPACE, f"{episode_id}:{role}")


def _audit(
    audit: AuditOutput,
    *,
    event_type: str,
    subject_id: str,
    at: datetime,
    reason_codes: tuple[str, ...],
    metadata: Mapping[str, str | int | float | bool | None] | None = None,
) -> None:
    audit.write(
        AuditEvent(
            event_type=event_type,
            subject_id=subject_id,
            occurred_at=at,
            reason_codes=reason_codes,
            metadata=metadata or {},
        )
    )


class _EpisodeCommand:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
    ) -> None:
        self._uow = uow
        self._episodes = episodes
        self._catalog = catalog
        self._controller = controller
        self._publisher: LearnerEvidencePublisher | None = None
        self._consent: ConsentStore | None = None
        self._summaries: SkillSummaryStore | None = None
        self._mastery: MasteryEvidenceGateway | None = None
        self._learner_state: LearnerStateGateway | None = None

    def _run(self, work: Callable[[], EpisodeState]) -> EpisodeState:
        return run_unit(self._uow, work)

    def _load(self, episode_id: EpisodeId) -> EpisodeState:
        return self._episodes.get(episode_id)

    def _save(self, state: EpisodeState) -> EpisodeState:
        return self._episodes.save(state)

    def _response(
        self,
        *,
        episode_id: EpisodeId,
        role: str,
        item: ItemDefinition,
        option_id: str,
        phase: str,
        support_state: str,
        submitted_at: datetime,
    ) -> ItemResponseEvidence:
        option = item.option(option_id)
        correct = option.option_id == item.correct_option_id
        return ItemResponseEvidence(
            response_id=_child_id(episode_id, role),
            item_id=ItemId(item.item_id),
            item_version=item.content_version,
            phase=phase,
            support_state=support_state,
            answer={"option_id": option_id},
            is_correct=correct,
            score=1.0 if correct else 0.0,
            submitted_at=submitted_at,
        )

    def _record_attempt(
        self,
        state: EpisodeState,
        response: ItemResponseEvidence,
        *,
        response_time_ms: int | None,
        support_exposure: str,
    ) -> None:
        records: LearningRecordStore = self._uow.learning_records
        records.record_attempt(
            GamificationAttempt(
                attempt_id=response.response_id,
                learner_id=state.episode.learner_id,
                item_id=response.item_id,
                skill_ids=(state.episode.skill_id,),
                language=state.language,
                correct=response.is_correct,
                score=response.score,
                response_time_ms=response_time_ms,
                support_exposure=support_exposure,
                attempted_at=response.submitted_at,
                contract_version=_ATTEMPT_CONTRACT,
            )
        )
        if self._summaries is not None:
            UpdateLearnerSkillSummary(self._summaries).record_attempt(
                learner_id=state.episode.learner_id,
                skill_id=str(state.episode.skill_id),
                correct=response.is_correct,
                supported=response.support_state == "supported",
                at=response.submitted_at,
            )

    def _publish(
        self,
        state: EpisodeState,
        *,
        event_type: str,
        at: datetime,
        model_version: str,
        confidence: float | None,
        reference: Mapping[str, str],
        payload: Mapping[str, float | int | bool | str | None],
    ) -> None:
        if self._publisher is None:
            return
        learner_id = state.episode.learner_id
        if self._consent is None or not research_consent_granted(self._consent, learner_id, at):
            _audit(
                self._uow.audit,
                event_type="learner_evidence_withheld",
                subject_id=str(state.episode.episode_id),
                at=at,
                reason_codes=("CONSENT_SCOPE_MISSING",),
                metadata={"event_type": event_type},
            )
            return
        universal = self._catalog.universal_skill_id(str(state.episode.skill_id))
        if universal is None:
            _audit(
                self._uow.audit,
                event_type="learner_evidence_withheld",
                subject_id=str(state.episode.episode_id),
                at=at,
                reason_codes=("CROSSWALK_MISSING",),
                metadata={"event_type": event_type},
            )
            return
        try:
            self._publisher.publish(
                LearnerEvidenceEvent(
                    event_type=event_type,
                    learner_id=learner_id,
                    skill_id=str(state.episode.skill_id),
                    universal_skill_id=universal,
                    timestamp=at,
                    model_version=model_version,
                    confidence=confidence,
                    evidence_reference=reference,
                    payload=payload,
                    contract_version="gamification-learner-evidence-v2",
                )
            )
        except Exception:  # noqa: BLE001  # a publisher failure is withheld evidence, not an episode crash
            _audit(
                self._uow.audit,
                event_type="learner_evidence_withheld",
                subject_id=str(state.episode.episode_id),
                at=at,
                reason_codes=("EVIDENCE_PUBLISH_FAILED",),
                metadata={"event_type": event_type},
            )


class OpenAdaptiveEpisode(_EpisodeCommand):
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
        templates: TemplateCompatibilityTable,
    ) -> None:
        super().__init__(uow=uow, episodes=episodes, catalog=catalog, controller=controller)
        self._templates = templates

    def execute(self, command: OpenAdaptiveEpisodeCommand) -> EpisodeState:
        return self._run(lambda: self._open(command))

    def _open(self, command: OpenAdaptiveEpisodeCommand) -> EpisodeState:
        item = self._catalog.item(command.item_id)
        if item.skill_id != str(command.skill_id):
            raise EpisodeFlowError("SKILL_MISMATCH")
        selection = self._templates.select_template(
            item, command.device_capabilities, command.variation_seed
        )
        response = self._response(
            episode_id=command.episode_id,
            role="baseline",
            item=item,
            option_id=command.selected_option_id,
            phase="baseline",
            support_state="unsupported",
            submitted_at=command.submitted_at,
        )
        episode = AdaptiveEpisode.create(
            episode_id=command.episode_id,
            learner_id=command.learner_id,
            skill_id=command.skill_id,
            created_at=command.submitted_at,
            protocol_version=ADAPTIVE_EPISODE_PROTOCOL,
        )
        episode = episode.transition_to(EpisodePhase.BASELINE_RESERVED, at=command.submitted_at)
        episode = episode.transition_to(EpisodePhase.BASELINE_ACTIVE, at=command.submitted_at)
        episode = episode.transition_to(EpisodePhase.BASELINE_SCORED, at=command.submitted_at)
        state = EpisodeState(
            episode=episode,
            session_id=command.session_id,
            taxonomy_version=command.taxonomy_version,
            language=command.language,
            trigger_type="pending",
            baseline_template=selection.template_key,
            template_reason=selection.reason_code,
            variation_seed=command.variation_seed,
            baseline_response=response,
            baseline_response_time_ms=command.response_time_ms,
            learner_requested_help=command.learner_requested_help,
            decision_mode=command.decision_mode,
        )
        self._record_attempt(
            state, response, response_time_ms=command.response_time_ms, support_exposure="none"
        )
        _audit(
            self._uow.audit,
            event_type="baseline_recorded",
            subject_id=str(command.episode_id),
            at=command.submitted_at,
            reason_codes=(selection.reason_code,),
            metadata={
                "template": selection.template_key,
                "phase": "baseline",
                "support_state": "unsupported",
                "variation_seed": command.variation_seed,
            },
        )
        self._episodes.insert(state)
        self._publish(
            state,
            event_type="attempt_summary",
            at=command.submitted_at,
            model_version="gamification-attempt-v1",
            confidence=None,
            reference={
                "episode_id": str(command.episode_id),
                "attempt_id": str(response.response_id),
                "session_id": str(command.session_id),
                "presentation_id": str(response.response_id),
                "item_revision": response.item_version,
            },
            payload={
                "unsupported_score": response.score,
                "response_time_ms": command.response_time_ms,
                "supported": False,
                "correct": response.is_correct,
                "difficulty": _difficulty_band(item.difficulty),
                "difficulty_numeric": item.difficulty,
                "difficulty_mapping_version": "pilot-difficulty-v1",
                "hint_count": 0,
                "environment": "development",
                "model_ingestion_eligible": False,
                "measurement_role": "unsupported_before",
                "earned_score": response.score,
                "maximum_score": 1.0,
            },
        )
        return state


class AssessStruggle(_EpisodeCommand):
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
        trigger: StruggleTrigger,
    ) -> None:
        super().__init__(uow=uow, episodes=episodes, catalog=catalog, controller=controller)
        self._trigger = trigger

    def execute(self, command: AssessStruggleCommand) -> EpisodeState:
        return self._run(lambda: self._assess(command))

    def _assess(self, command: AssessStruggleCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        if state.baseline_response is None or state.baseline_response.phase != "baseline":
            raise EpisodeFlowError("BASELINE_NOT_RECORDED")
        if state.baseline_response.support_state != "unsupported":
            raise EpisodeFlowError("BASELINE_NOT_UNSUPPORTED")
        evidence = self._support_evidence(state, command)
        decision = self._trigger.evaluate(evidence)
        if decision.fired:
            episode = state.episode.transition_to(EpisodePhase.GAMEPLAY_ACTIVE, at=command.at)
            episode = episode.transition_to(EpisodePhase.DIFFICULTY_DETECTED, at=command.at)
            event_type = "struggle_detected"
        else:
            episode = state.episode.transition_to(
                EpisodePhase.ABANDONED, at=command.at, reason="NO_STRUGGLE_DETECTED"
            )
            event_type = "episode_abandoned"
        updated = replace(
            state,
            episode=episode,
            trigger_type=decision.trigger_type,
            trigger_reasons=decision.reason_codes,
            trigger_missing_inputs=decision.missing_inputs,
            trigger_skipped_rules=decision.skipped_rules,
            trigger_config_version=decision.config_version,
            closed_at=command.at if episode.phase is EpisodePhase.ABANDONED else None,
        )
        _audit(
            self._uow.audit,
            event_type=event_type,
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=decision.reason_codes or ("NO_STRUGGLE_DETECTED",),
            metadata={
                "config_version": decision.config_version,
                "missing_inputs": ",".join(decision.missing_inputs),
            },
        )
        if decision.fired:
            self._publish(
                updated,
                event_type="detected_difficulty",
                at=command.at,
                model_version=decision.config_version,
                confidence=None,
                reference={"episode_id": str(command.episode_id)},
                payload={"trigger_type": decision.trigger_type},
            )
        return self._save(updated)

    def _support_evidence(self, state: EpisodeState, command: AssessStruggleCommand):
        evidence = command.evidence
        if self._learner_state is None:
            return evidence
        cutoff = command.at - timedelta(milliseconds=self._trigger.config.support_need_max_age_ms)
        try:
            try:
                looked_up = self._learner_state.get_support_evidence(
                    learner_id=state.episode.learner_id,
                    skill_id=state.episode.skill_id,
                    observed_no_earlier_than=cutoff,
                    session_id=state.session_id,
                )
            except TypeError:
                # Transitional compatibility for a v1 in-process adapter. Production adapters
                # implement the session-aware call above.
                looked_up = self._learner_state.get_support_evidence(
                    learner_id=state.episode.learner_id,
                    skill_id=state.episode.skill_id,
                    observed_no_earlier_than=cutoff,
                )
        except Exception:  # noqa: BLE001  # a missing learner-state signal is a recorded absence
            looked_up = None
            _audit(
                self._uow.audit,
                event_type="support_need_missing",
                subject_id=str(command.episode_id),
                at=command.at,
                reason_codes=("LEARNER_STATE_UNAVAILABLE",),
                metadata={},
            )
        if looked_up is None:
            return replace(
                evidence,
                learner_support_need=None,
                learner_state_observed_at=None,
                learner_state_uncertain=False,
                learner_state_recommended_action=None,
            )
        return replace(
            evidence,
            learner_support_need=looked_up.support_need,
            learner_state_observed_at=looked_up.observed_at,
            learner_state_uncertain=looked_up.uncertain,
            learner_state_recommended_action=looked_up.recommended_action,
        )


class InferMisconceptionBeliefs(_EpisodeCommand):
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
        predictor: MisconceptionPredictor,
        features: FeatureBuilder | None = None,
    ) -> None:
        super().__init__(uow=uow, episodes=episodes, catalog=catalog, controller=controller)
        self._predictor = predictor
        self._features = features or FeatureBuilder()

    def execute(self, command: InferMisconceptionBeliefsCommand) -> EpisodeState:
        return self._run(lambda: self._infer(command))

    def _infer(self, command: InferMisconceptionBeliefsCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        response = state.baseline_response
        if response is None:
            raise EpisodeFlowError("BASELINE_NOT_RECORDED")
        item = self._catalog.item(str(response.item_id))
        option_id = str(response.answer["option_id"])
        option = item.option(option_id)
        sources = dict(command.source_as_of)
        sources.setdefault("baseline_response", response.submitted_at)
        mastery_probability, mastery_uncertainty = self._mastery_features(state, command)
        snapshot = self._features.build(
            DecisionFeatureInput(
                learner_id=state.episode.learner_id,
                skill_id=state.episode.skill_id,
                captured_at=command.at,
                protocol_version=ProtocolVersion(_FEATURE_PROTOCOL),
                skill_taxonomy_version=TaxonomyVersion(state.taxonomy_version),
                misconception_catalogue_version=self._catalog.misconception_catalogue_version(),
                support_catalogue_version=self._catalog.support_catalogue_version(),
                current_score=response.score,
                recent_correctness=command.recent_correctness,
                attempt_count=command.attempt_count,
                response_time_ms=state.baseline_response_time_ms,
                hint_requests=1 if state.learner_requested_help else 0,
                structured_error_code=None if response.is_correct else option.misconception_code,
                mastery_probability=mastery_probability,
                mastery_uncertainty=mastery_uncertainty,
                learner_support_need=command.learner_support_need,
                learner_state_reliability=command.learner_state_reliability,
                source_as_of=sources,
                selected_option_id=option_id,
                distractor_misconception_code=option.misconception_code,
                item_difficulty=item.difficulty,
                template_key=state.baseline_template,
            )
        )
        belief = self._predictor.predict(snapshot)
        episode = state.episode.transition_to(EpisodePhase.MISCONCEPTION_ESTIMATED, at=command.at)
        _audit(
            self._uow.audit,
            event_type="misconception_recorded",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=belief.reason_codes,
            metadata={"model_version": belief.model_version, "abstained": belief.abstained},
        )
        self._publish(
            replace(state, episode=episode),
            event_type="misconception_probabilities",
            at=command.at,
            model_version=belief.model_version,
            confidence=belief.confidence,
            reference={"episode_id": str(command.episode_id)},
            payload={
                **{
                    f"belief_{code}": probability
                    for code, probability in belief.probabilities.items()
                },
                "catalogue_version": belief.catalogue_version,
                "abstained": belief.abstained,
            },
        )
        return self._save(replace(state, episode=episode, feature_snapshot=snapshot, belief=belief))

    def _mastery_features(
        self, state: EpisodeState, command: InferMisconceptionBeliefsCommand
    ) -> tuple[float | None, float | None]:
        if self._mastery is None:
            return command.mastery_probability, command.mastery_uncertainty
        try:
            found = self._mastery.get_mastery(
                learner_id=state.episode.learner_id, skill_id=state.episode.skill_id
            )
        except Exception:  # noqa: BLE001  # a missing mastery signal is a recorded absence
            found = None
            _audit(
                self._uow.audit,
                event_type="mastery_missing",
                subject_id=str(command.episode_id),
                at=command.at,
                reason_codes=("MASTERY_UNAVAILABLE",),
                metadata={},
            )
        if found is None:
            return None, None
        return found.mastery_probability, found.uncertainty


class SelectSupportAction(_EpisodeCommand):
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
        selector: SupportSelector,
        allow_draft: bool,
    ) -> None:
        super().__init__(uow=uow, episodes=episodes, catalog=catalog, controller=controller)
        self._selector = selector
        self._allow_draft = allow_draft

    def execute(self, command: SelectSupportActionCommand) -> EpisodeState:
        return self._run(lambda: self._select(command))

    def _select(self, command: SelectSupportActionCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        if (
            state.feature_snapshot is None
            or state.belief is None
            or state.baseline_response is None
        ):
            raise EpisodeFlowError("MISCONCEPTION_NOT_RECORDED")
        mode = command.mode or state.decision_mode
        candidates = self._policy_candidates(str(state.episode.skill_id))
        context = self._bandit_context(state)
        decision = self._selector.decide(
            episode_id=command.episode_id,
            snapshot=state.feature_snapshot,
            belief=state.belief,
            candidates=candidates,
            language=state.language,
            seed=command.seed,
            decided_at=command.at,
            mode=mode,
            context=context,
        )
        decision, rejected = self._apply_leakage(state, decision)
        context_snapshot = policy_context_snapshot(state.feature_snapshot, context)
        decision = replace(decision, feature_snapshot_id=context_snapshot.snapshot_id)
        episode = state.episode.transition_to(EpisodePhase.SUPPORT_DECIDED, at=command.at)
        for action_id, failures in rejected:
            _audit(
                self._uow.audit,
                event_type="scaffold_rejected",
                subject_id=str(command.episode_id),
                at=command.at,
                reason_codes=("ANSWER_LEAKAGE", *failures),
                metadata={"action_id": action_id},
            )
        _audit(
            self._uow.audit,
            event_type="support_decided",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=decision.reason_codes,
            metadata={"action_id": str(decision.selected_action_id), "mode": str(mode)},
        )
        selected = next(
            candidate
            for candidate in decision.candidates
            if candidate.action_id == decision.selected_action_id
        )
        decided = replace(state, episode=episode, decision=decision)
        self._publish(
            decided,
            event_type="selected_scaffold",
            at=command.at,
            model_version=decision.policy_version,
            confidence=None,
            reference={
                "episode_id": str(command.episode_id),
                "decision_id": str(decision.decision_id),
            },
            payload={
                "action_id": str(decision.selected_action_id),
                "action_type": selected.action_type.value,
            },
        )
        return self._save(
            replace(
                decided,
                decision_mode=mode,
                policy_context_snapshot=context_snapshot,
            )
        )

    def _bandit_context(self, state: EpisodeState):
        assert state.feature_snapshot is not None
        assert state.belief is not None
        assert state.baseline_response is not None
        item = self._catalog.item(str(state.baseline_response.item_id))
        raw_mastery = state.feature_snapshot.values.get("mastery_probability")
        mastery = (
            float(raw_mastery)
            if isinstance(raw_mastery, (int, float)) and not isinstance(raw_mastery, bool)
            else None
        )
        builder = BanditContextBuilder(
            catalogue_codes=self._catalog.misconception_codes(),
            skill_ids=self._catalog.skill_ids(),
            mastery_gateway=FixedMasteryGateway(mastery),
        )
        return builder.build(
            snapshot=state.feature_snapshot,
            belief=state.belief,
            item=QuestionContext(
                skill_id=item.skill_id,
                difficulty=item.difficulty,
                response_format=item.response_format.value,
                template_key=item.default_template,
            ),
            history=SupportHistory.from_snapshot(state.feature_snapshot),
        )

    def _policy_candidates(self, skill_id: str):
        adjusted = []
        for candidate in self._catalog.support_candidates(skill_id):
            scaffold = self._catalog.scaffold(str(candidate.action_id))
            approved = scaffold.status is ContentStatus.APPROVED or (
                self._allow_draft and scaffold.status is ContentStatus.DRAFT
            )
            adjusted.append(replace(candidate, approved=approved))
        return tuple(adjusted)

    def _apply_leakage(self, state: EpisodeState, decision):
        item = self._catalog.item(str(state.baseline_response.item_id))
        eligible = sorted(
            (candidate for candidate in decision.candidates if candidate.eligible),
            key=lambda candidate: str(candidate.action_id),
        )
        rejected: list[tuple[str, tuple[str, ...]]] = []
        accepted = None
        for candidate in eligible:
            scaffold = self._catalog.scaffold(str(candidate.action_id))
            asset = self._catalog.asset(scaffold.content_asset_id)
            failures = self._controller.leakage_failures(scaffold, asset, item)
            if failures:
                rejected.append((str(candidate.action_id), failures))
                continue
            accepted = candidate
            break
        if accepted is None:
            raise EpisodeFlowError("ANSWER_LEAKAGE")
        if not rejected:
            return decision, rejected
        rejected_ids = {action_id for action_id, _failures in rejected}
        failure_by_id = dict(rejected)
        rebuilt = []
        for candidate in decision.candidates:
            action_id = str(candidate.action_id)
            if action_id in rejected_ids:
                rebuilt.append(
                    replace(
                        candidate,
                        eligible=False,
                        propensity=0.0,
                        reason_codes=("ANSWER_LEAKAGE", *failure_by_id[action_id]),
                    )
                )
            else:
                rebuilt.append(candidate)
        remaining = [candidate for candidate in rebuilt if candidate.eligible]
        total = sum(candidate.propensity for candidate in remaining)
        if total <= 0:
            rebuilt = [
                replace(candidate, propensity=1.0)
                if candidate.action_id == accepted.action_id
                else replace(candidate, propensity=0.0)
                if candidate.eligible
                else candidate
                for candidate in rebuilt
            ]
        else:
            rebuilt = [
                replace(candidate, propensity=candidate.propensity / total)
                if candidate.eligible
                else candidate
                for candidate in rebuilt
            ]
        return (
            replace(
                decision,
                selected_action_id=accepted.action_id,
                candidates=tuple(rebuilt),
                reason_codes=decision.reason_codes + ("LEAKAGE_FALLBACK",),
            ),
            rejected,
        )


class RecordSupportExposure(_EpisodeCommand):
    def execute(self, command: RecordSupportExposureCommand) -> EpisodeState:
        return self._run(lambda: self._record(command))

    def _record(self, command: RecordSupportExposureCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        self._controller.assert_no_active_scaffold(len(state.exposures))
        if state.decision is None or state.baseline_response is None:
            raise EpisodeFlowError("SUPPORT_NOT_DECIDED")
        scaffold = self._catalog.scaffold(str(state.decision.selected_action_id))
        self._controller.accept_for_delivery(
            scaffold, selected_action_id=str(state.decision.selected_action_id)
        )
        item = self._catalog.item(str(state.baseline_response.item_id))
        asset = self._catalog.asset(scaffold.content_asset_id)
        failures = self._controller.leakage_failures(scaffold, asset, item)
        if failures:
            raise EpisodeFlowError("ANSWER_LEAKAGE")
        budget = self._controller.budget_for(scaffold)
        status = self._controller.completion_status(
            budget, duration_ms=command.duration_ms, step_count=command.step_count
        )
        evidence = SupportExposureEvidence(
            exposure_id=_child_id(command.episode_id, f"exposure:{scaffold.scaffold_id}"),
            action_id=ActionId(scaffold.scaffold_id),
            delivery_status=status,
            presented_at=command.at,
            completed_at=command.at,
            duration_ms=command.duration_ms,
            render_version=scaffold.version,
            maximum_duration_ms=budget.maximum_duration_ms,
            maximum_number_of_steps=budget.maximum_number_of_steps,
        )
        record = SupportExposureRecord(
            evidence=evidence,
            maximum_duration_ms=budget.maximum_duration_ms,
            maximum_number_of_steps=budget.maximum_number_of_steps,
            interaction_count=command.step_count,
        )
        supported = state.supported_responses
        if command.supported_item_id and command.supported_option_id:
            supported_item = self._catalog.item(command.supported_item_id)
            supported_response = self._response(
                episode_id=command.episode_id,
                role=f"supported:{len(supported) + 1}",
                item=supported_item,
                option_id=command.supported_option_id,
                phase="supported",
                support_state="supported",
                submitted_at=command.at,
            )
            self._record_attempt(
                state,
                supported_response,
                response_time_ms=None,
                support_exposure=scaffold.scaffold_id,
            )
            supported = (*supported, supported_response)
        episode = self._controller.deliver(state.episode, at=command.at)
        _audit(
            self._uow.audit,
            event_type="support_delivered",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=(status,),
            metadata={
                "action_id": scaffold.scaffold_id,
                "maximum_duration_ms": budget.maximum_duration_ms,
                "maximum_number_of_steps": budget.maximum_number_of_steps,
                "duration_ms": command.duration_ms,
                "step_count": command.step_count,
            },
        )
        return self._save(
            replace(
                state,
                episode=episode,
                exposures=(*state.exposures, record),
                supported_responses=supported,
            )
        )


class WithdrawSupport(_EpisodeCommand):
    def execute(self, command: WithdrawSupportCommand) -> EpisodeState:
        return self._run(lambda: self._withdraw(command))

    def _withdraw(self, command: WithdrawSupportCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        if not state.exposures:
            raise EpisodeFlowError("SUPPORT_NOT_DELIVERED")
        episode = self._controller.withdraw(state.episode, at=command.at)
        _audit(
            self._uow.audit,
            event_type="support_withdrawn",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=("SUPPORT_WITHDRAWN",),
            metadata={"support_withdrawn_at": command.at.isoformat()},
        )
        return self._save(replace(state, episode=episode, withdrawn_at=command.at))


class ScheduleUnsupportedVerification(_EpisodeCommand):
    def execute(self, command: ScheduleUnsupportedVerificationCommand) -> EpisodeState:
        return self._run(lambda: self._schedule(command))

    def _schedule(self, command: ScheduleUnsupportedVerificationCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        self._controller.assert_withdrawn(state.withdrawn_at)
        if state.baseline_response is None or state.baseline_template is None:
            raise EpisodeFlowError("BASELINE_NOT_RECORDED")
        baseline = self._catalog.item(str(state.baseline_response.item_id))
        seen = self._uow.learning_records.seen_item_ids(learner_id=state.episode.learner_id)
        try:
            verification = self._controller.choose_verification_item(
                self._catalog.items_in_group(baseline.parallel_group_id),
                baseline_item_id=baseline.item_id,
                seen_item_ids=seen,
                required_template=state.baseline_template,
            )
        except EpisodeFlowError as error:
            if error.code != "VERIFICATION_PAIR_UNAVAILABLE":
                raise
            return self._invalidate(state, command.at, error.code)
        template = require_same_template(state.baseline_template, verification)
        group = self._catalog.parallel_group(baseline.parallel_group_id)
        overlap = answer_overlap(baseline, verification)
        pair = VerificationPairEvidence(
            pair_id=_child_id(command.episode_id, "verification-pair"),
            baseline_item_id=ItemId(baseline.item_id),
            baseline_item_version=baseline.content_version,
            verification_item_id=ItemId(verification.item_id),
            verification_item_version=verification.content_version,
            equivalence_version=group.equivalence_version,
            review_status=group.status.value,
            unseen_verification_item=True,
            answer_overlap=overlap,
        )
        episode = self._controller.schedule(state.episode, at=command.at)
        _audit(
            self._uow.audit,
            event_type="verification_scheduled",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=("UNSEEN_PARALLEL_ITEM",),
            metadata={
                "verification_item_id": verification.item_id,
                "template": template,
                "unseen_verification_item": True,
                "answer_overlap": overlap,
            },
        )
        return self._save(replace(state, episode=episode, verification_pair=pair))

    def _invalidate(self, state: EpisodeState, at: datetime, reason: str) -> EpisodeState:
        episode = state.episode.transition_to(EpisodePhase.INVALIDATED, at=at, reason=reason)
        _audit(
            self._uow.audit,
            event_type="episode_invalidated",
            subject_id=str(state.episode.episode_id),
            at=at,
            reason_codes=(reason,),
        )
        return self._save(replace(state, episode=episode, closed_at=at))


class RecordVerificationResponse(_EpisodeCommand):
    def execute(self, command: RecordVerificationResponseCommand) -> EpisodeState:
        return self._run(lambda: self._record(command))

    def _record(self, command: RecordVerificationResponseCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        if state.verification_pair is None:
            raise EpisodeFlowError("VERIFICATION_NOT_SCHEDULED")
        item = self._catalog.item(str(state.verification_pair.verification_item_id))
        if state.baseline_template is not None:
            require_same_template(state.baseline_template, item)
        response = self._response(
            episode_id=command.episode_id,
            role="verification",
            item=item,
            option_id=command.selected_option_id,
            phase="verification",
            support_state="unsupported",
            submitted_at=command.at,
        )
        self._record_attempt(
            state, response, response_time_ms=command.response_time_ms, support_exposure="none"
        )
        episode = state.episode.transition_to(EpisodePhase.INDEPENDENT_CHECK_SCORED, at=command.at)
        _audit(
            self._uow.audit,
            event_type="verification_recorded",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=("UNSUPPORTED_VERIFICATION",),
            metadata={"template": state.baseline_template, "phase": "verification"},
        )
        updated = replace(state, episode=episode, verification_response=response)
        self._publish(
            updated,
            event_type="attempt_summary",
            at=command.at,
            model_version="gamification-attempt-v1",
            confidence=None,
            reference={
                "episode_id": str(command.episode_id),
                "attempt_id": str(response.response_id),
                "session_id": str(state.session_id),
                "presentation_id": str(response.response_id),
                "item_revision": response.item_version,
            },
            payload={
                "unsupported_score": response.score,
                "response_time_ms": command.response_time_ms,
                "supported": False,
                "correct": response.is_correct,
                "difficulty": _difficulty_band(item.difficulty),
                "difficulty_numeric": item.difficulty,
                "difficulty_mapping_version": "pilot-difficulty-v1",
                "hint_count": 0,
                "environment": "development",
                "model_ingestion_eligible": False,
                "measurement_role": "unsupported_after",
                "earned_score": response.score,
                "maximum_score": 1.0,
            },
        )
        return self._save(updated)


class CalculateIndependenceOutcome(_EpisodeCommand):
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        episodes: EpisodeRepository,
        catalog: PilotContentCatalog,
        controller: ScaffoldController,
        calculator: IndependenceGainCalculator,
        allow_draft: bool,
        predictor: MisconceptionPredictor | None = None,
    ) -> None:
        super().__init__(uow=uow, episodes=episodes, catalog=catalog, controller=controller)
        self._calculator = calculator
        self._allow_draft = allow_draft
        self._predictor = predictor

    def execute(self, command: CalculateIndependenceOutcomeCommand) -> EpisodeState:
        return self._run(lambda: self._calculate(command))

    def _calculate(self, command: CalculateIndependenceOutcomeCommand) -> EpisodeState:
        state = self._load(command.episode_id)
        if (
            state.baseline_response is None
            or state.verification_response is None
            or state.verification_pair is None
            or state.withdrawn_at is None
            or not state.exposures
        ):
            raise EpisodeFlowError("VERIFICATION_NOT_RECORDED")
        baseline = self._catalog.item(str(state.baseline_response.item_id))
        verification = self._catalog.item(str(state.verification_response.item_id))
        group = self._catalog.parallel_group(baseline.parallel_group_id)
        exposure = state.exposures[0]
        structural = (
            baseline.skill_id == verification.skill_id
            and baseline.cognitive_operation == verification.cognitive_operation
            and baseline.difficulty == verification.difficulty
            and baseline.response_format is verification.response_format
        )
        # Draft pilot pairs are not educator-approved. allow_draft accepts a structural
        # match for the engineering calculator only; the stored review_status stays draft.
        approved = group.status is ContentStatus.APPROVED or (self._allow_draft and structural)
        equivalence = EquivalenceEvidence(
            primary_skill_match=baseline.skill_id == verification.skill_id,
            cognitive_operation_match=(
                baseline.cognitive_operation == verification.cognitive_operation
            ),
            difficulty_band_match=baseline.difficulty == verification.difficulty,
            response_format_match=baseline.response_format is verification.response_format,
            language_reviewed=baseline.medium == verification.medium == state.language,
            # Pilot items have no expected-time field, so there is nothing to mismatch.
            expected_time_match=True,
            unseen_verification_item=state.verification_pair.unseen_verification_item,
            answer_overlap_acceptable=state.verification_pair.answer_overlap == 0.0,
            equivalence_version=group.equivalence_version,
            approved=approved,
        )
        result = self._calculator.calculate(
            IndependenceGainInput(
                baseline_score=state.baseline_response.score,
                verification_score=state.verification_response.score,
                baseline_support_state=EvidenceSupportState.UNSUPPORTED,
                verification_support_state=EvidenceSupportState.UNSUPPORTED,
                equivalence=equivalence,
                support_delivered=True,
                support_completed=exposure_counts_as_completed(exposure.evidence.delivery_status),
                support_withdrawn_at=state.withdrawn_at,
                verification_started_at=state.verification_response.submitted_at,
                idle_time_ms=command.idle_time_ms,
                maximum_idle_time_ms=command.maximum_idle_time_ms,
            )
        )
        outcome = IndependenceOutcomeEvidence(
            outcome_id=_child_id(command.episode_id, "outcome"),
            validity=result.validity.value,
            baseline_score=state.baseline_response.score,
            verification_score=state.verification_response.score,
            raw_independence_gain=result.raw_gain,
            invalid_reason=",".join(result.invalid_reasons) or None,
            formula_version=result.formula_version,
            calculated_at=command.at,
            misconception_resolution=self._resolution(state, command.at),
        )
        episode = state.episode.transition_to(EpisodePhase.REWARD_VALIDATED, at=command.at)
        episode = episode.transition_to(EpisodePhase.COMPLETED, at=command.at)
        _audit(
            self._uow.audit,
            event_type="outcome_recorded",
            subject_id=str(command.episode_id),
            at=command.at,
            reason_codes=result.invalid_reasons or ("INDEPENDENCE_GAIN_VALID",),
            metadata={"formula_version": result.formula_version, "validity": result.validity.value},
        )
        if (
            self._summaries is not None
            and result.validity is OutcomeValidity.VALID
            and result.raw_gain is not None
        ):
            UpdateLearnerSkillSummary(self._summaries).record_valid_gain(
                learner_id=state.episode.learner_id,
                skill_id=str(state.episode.skill_id),
                raw_gain=result.raw_gain,
                at=command.at,
            )
        dependency = None
        if self._summaries is not None:
            summary = self._summaries.get(
                learner_id=state.episode.learner_id, skill_id=str(state.episode.skill_id)
            )
            if summary is not None:
                dependency = summary.support_dependency_index
        completed = replace(state, episode=episode, outcome=outcome)
        gain_payload: dict[str, float | int | bool | str | None] = {
            "unsupported_before_score": state.baseline_response.score,
            "unsupported_after_score": state.verification_response.score,
            "validity": result.validity.value,
            "support_dependency_index": dependency,
        }
        if result.validity is OutcomeValidity.VALID and result.raw_gain is not None:
            gain_payload["independence_gain"] = result.raw_gain
        self._publish(
            completed,
            event_type="independence_gain",
            at=command.at,
            model_version=result.formula_version,
            confidence=None,
            reference={
                "episode_id": str(command.episode_id),
                "outcome_id": str(outcome.outcome_id),
            },
            payload=gain_payload,
        )
        return self._save(replace(completed, closed_at=command.at))

    def _resolution(self, state: EpisodeState, at: datetime) -> float | None:
        """Infer again from the verification item. The snapshot is an outcome, not a feature."""

        if self._predictor is None or state.belief is None or state.verification_response is None:
            return None
        response = state.verification_response
        item = self._catalog.item(str(response.item_id))
        option = item.option(str(response.answer["option_id"]))
        measured = FeatureSnapshotRecord(
            snapshot_id=FeatureSnapshotId(
                uuid5(_NAMESPACE, f"{state.episode.episode_id}:outcome-measurement")
            ),
            learner_id=state.episode.learner_id,
            skill_id=state.episode.skill_id,
            captured_at=at,
            protocol_version=ProtocolVersion("outcome-measurement-v1"),
            taxonomy_version=TaxonomyVersion(state.taxonomy_version),
            feature_definition_version=FEATURE_DEFINITION_VERSION,
            values={
                "misconception_catalogue_version": self._catalog.misconception_catalogue_version(),
                "structured_error_code": None if response.is_correct else option.misconception_code,
                "current_score": response.score,
            },
            source_as_of={"verification_response": response.submitted_at.isoformat()},
            purpose="outcome_measurement",
        )
        if measured.purpose in {"model_decision", "policy_context"}:
            return None
        if "misconception_resolution" in measured.values:
            return None
        posterior = self._predictor.predict(measured)
        return misconception_resolution(state.belief.probabilities, posterior.probabilities)


@dataclass(frozen=True, slots=True)
class EpisodeUseCases:
    open_episode: OpenAdaptiveEpisode
    assess_struggle: AssessStruggle
    infer_beliefs: InferMisconceptionBeliefs
    select_support: SelectSupportAction
    record_exposure: RecordSupportExposure
    withdraw_support: WithdrawSupport
    schedule_verification: ScheduleUnsupportedVerification
    record_verification: RecordVerificationResponse
    calculate_outcome: CalculateIndependenceOutcome


def wire_episode_use_cases(
    *,
    uow: UnitOfWork,
    episodes: EpisodeRepository,
    catalog: PilotContentCatalog,
    predictor: MisconceptionPredictor,
    selector: SupportSelector,
    calculator: IndependenceGainCalculator,
    allow_draft: bool,
    trigger: StruggleTrigger | None = None,
    templates: TemplateCompatibilityTable | None = None,
    publisher: LearnerEvidencePublisher | None = None,
    consent: ConsentStore | None = None,
    summaries: SkillSummaryStore | None = None,
    mastery: MasteryEvidenceGateway | None = None,
    learner_state: LearnerStateGateway | None = None,
) -> EpisodeUseCases:
    controller = ScaffoldController(allow_draft=allow_draft)
    table = templates or TemplateCompatibilityTable(
        catalog.template_rules(),
        table_version=catalog.template_table_version(),
    )
    shared = {"uow": uow, "episodes": episodes, "catalog": catalog, "controller": controller}
    cases = EpisodeUseCases(
        open_episode=OpenAdaptiveEpisode(templates=table, **shared),
        assess_struggle=AssessStruggle(trigger=trigger or StruggleTrigger(), **shared),
        infer_beliefs=InferMisconceptionBeliefs(predictor=predictor, **shared),
        select_support=SelectSupportAction(selector=selector, allow_draft=allow_draft, **shared),
        record_exposure=RecordSupportExposure(**shared),
        withdraw_support=WithdrawSupport(**shared),
        schedule_verification=ScheduleUnsupportedVerification(**shared),
        record_verification=RecordVerificationResponse(**shared),
        calculate_outcome=CalculateIndependenceOutcome(
            calculator=calculator, allow_draft=allow_draft, predictor=predictor, **shared
        ),
    )
    for command in (
        cases.open_episode,
        cases.assess_struggle,
        cases.infer_beliefs,
        cases.select_support,
        cases.record_exposure,
        cases.withdraw_support,
        cases.schedule_verification,
        cases.record_verification,
        cases.calculate_outcome,
    ):
        command._publisher = publisher
        command._consent = consent
        command._summaries = summaries
        command._mastery = mastery
        command._learner_state = learner_state
    return cases
