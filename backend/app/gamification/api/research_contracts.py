"""Strict, versioned episode research contracts.

These schemas describe boundaries only. They do not implement curriculum content, model
inference, persistence, HTTP routes, or a mobile interface.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)

from app.gamification.domain.types import (
    AssistanceState,
    EpisodePhase,
    ExperimentMode,
    MeasurementRole,
)

RESEARCH_CONTRACT_VERSION = "gamification-research-contracts-v1"
EVENT_SCHEMA_VERSION = "gamification-event-envelope-v1"
RAW_IG_FORMULA_VERSION = "raw-independence-gain-v1"

Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, strict=True),
]
Version = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        strict=True,
    ),
]
Probability = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
NonNegativeScore = Annotated[StrictFloat, Field(ge=0.0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
SequenceNumber = Annotated[StrictInt, Field(ge=1)]


class ResearchContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal[RESEARCH_CONTRACT_VERSION] = RESEARCH_CONTRACT_VERSION


class LearnerEligibilityContract(ResearchContract):
    learner_id: UUID
    grade: Literal[5]
    curriculum_medium: Literal["si"]
    pseudonymous: Literal[True]
    consent_eligibility_reference: Identifier
    research_eligible: StrictBool
    checked_at: AwareDatetime


class LearningSessionContract(ResearchContract):
    session_id: UUID
    learner_id: UUID
    grade: Literal[5]
    curriculum_medium: Literal["si"]
    app_version: Version
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    offline_capable: StrictBool

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        return self


class EpisodeContract(ResearchContract):
    episode_id: UUID
    session_id: UUID
    learner_id: UUID
    skill_id: Identifier
    skill_version: Version
    protocol_version: Literal["adaptive-episode-v1"]
    experiment_mode: ExperimentMode
    phase: EpisodePhase
    server_authoritative: Literal[True]
    created_at: AwareDatetime
    transitioned_at: AwareDatetime

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        if self.transitioned_at < self.created_at:
            raise ValueError("transitioned_at cannot precede created_at")
        return self


_UNSUPPORTED_ROLES = {
    MeasurementRole.UNSUPPORTED_BEFORE,
    MeasurementRole.UNSUPPORTED_AFTER,
    MeasurementRole.RETENTION,
}


class PresentationContract(ResearchContract):
    presentation_id: UUID
    episode_id: UUID
    item_revision_id: Identifier
    parallel_family_id: Identifier | None
    sequence: SequenceNumber
    measurement_role: MeasurementRole
    assistance_state: AssistanceState
    role_assigned_at_presentation: Literal[True]
    grade: Literal[5]
    curriculum_medium: Literal["si"]
    opened_at: AwareDatetime
    closed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_assistance_role(self) -> Self:
        if (
            self.measurement_role in _UNSUPPORTED_ROLES
            and self.assistance_state is not AssistanceState.NONE
        ):
            raise ValueError("unsupported and retention roles require assistance_state=none")
        if (
            self.measurement_role is MeasurementRole.SUPPORTED_PRACTICE
            and self.assistance_state is AssistanceState.NONE
        ):
            raise ValueError("supported_practice requires explicit assistance")
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot precede opened_at")
        return self


Scalar = StrictBool | StrictInt | StrictFloat | Identifier | None


class AttemptContract(ResearchContract):
    attempt_id: UUID
    presentation_id: UUID
    attempt_number: Annotated[StrictInt, Field(ge=1, le=100)]
    response: dict[Identifier, Scalar] = Field(min_length=1, max_length=32)
    assistance_state: AssistanceState
    measurement_role: MeasurementRole
    active_response_ms: NonNegativeInt | None
    wall_clock_ms: NonNegativeInt | None
    submitted_at: AwareDatetime

    @model_validator(mode="after")
    def validate_assistance_role(self) -> Self:
        if (
            self.measurement_role in _UNSUPPORTED_ROLES
            and self.assistance_state is not AssistanceState.NONE
        ):
            raise ValueError("unsupported attempts require assistance_state=none")
        if (
            self.measurement_role is MeasurementRole.SUPPORTED_PRACTICE
            and self.assistance_state is AssistanceState.NONE
        ):
            raise ValueError("supported attempts require explicit assistance")
        return self


class ScoreInputContract(ResearchContract):
    scoring_request_id: UUID
    attempt_id: UUID
    item_revision_id: Identifier
    rubric_version: Version
    response: dict[Identifier, Scalar] = Field(min_length=1, max_length=32)
    requested_at: AwareDatetime


class ScoreResultContract(ResearchContract):
    scoring_request_id: UUID
    attempt_id: UUID
    score: NonNegativeScore
    maximum_score: Annotated[StrictFloat, Field(gt=0.0)]
    correct: StrictBool | None
    rubric_version: Version
    scoring_version: Version
    server_authoritative: Literal[True]
    scored_at: AwareDatetime

    @model_validator(mode="after")
    def validate_score(self) -> Self:
        if self.score > self.maximum_score:
            raise ValueError("score cannot exceed maximum_score")
        return self


class DifficultyEvidenceContract(ResearchContract):
    evidence_id: UUID
    episode_id: UUID
    contributing_event_ids: tuple[UUID, ...] = Field(min_length=1, max_length=128)
    feature_values: dict[Identifier, StrictFloat | StrictInt | StrictBool] = Field(max_length=64)
    missingness: dict[Identifier, StrictBool] = Field(max_length=64)
    evidence_window_version: Version
    captured_at: AwareDatetime


class DifficultyTriggerContract(ResearchContract):
    trigger_id: UUID
    episode_id: UUID
    evidence_id: UUID
    fired: StrictBool
    eligible_for_support: StrictBool
    rule_version: Version
    threshold_values: dict[Identifier, StrictFloat] = Field(max_length=32)
    severity: Probability | None
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)
    server_authoritative: Literal[True]
    evaluated_at: AwareDatetime


class ExternalEvidenceContract(ResearchContract):
    source: Literal["knowledge_tracing", "multimodal_learner_state", "verified_tutoring"]
    source_version: Version
    observed_at: AwareDatetime | None
    expires_at: AwareDatetime | None
    reliability: Probability | None
    missing: StrictBool
    value: dict[Identifier, Scalar] | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_freshness_and_missingness(self) -> Self:
        if self.missing:
            if self.value is not None or self.reliability is not None or self.observed_at is not None:
                raise ValueError("missing external evidence cannot contain observations")
        else:
            if self.value is None or self.reliability is None or self.observed_at is None:
                raise ValueError("available external evidence requires value, reliability, and time")
            if self.expires_at is not None and self.expires_at <= self.observed_at:
                raise ValueError("expires_at must be later than observed_at")
        return self


class MisconceptionBeliefContract(ResearchContract):
    belief_snapshot_id: UUID
    learner_id: UUID
    skill_id: Identifier
    episode_id: UUID
    item_revision_id: Identifier
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1, max_length=128)
    probabilities: dict[Identifier, Probability] = Field(min_length=1, max_length=128)
    model_version: Version
    mapping_version: Version
    evidence_window_version: Version
    low_confidence: StrictBool
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_distribution(self) -> Self:
        if "unknown_or_other" not in self.probabilities:
            raise ValueError("probabilities require unknown_or_other")
        if abs(sum(self.probabilities.values()) - 1.0) > 1e-9:
            raise ValueError("misconception probabilities must sum to 1")
        return self


class ScaffoldCandidateContract(ResearchContract):
    scaffold_id: Identifier
    scaffold_version: Version
    eligible: StrictBool
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)


class ScaffoldPredictionContract(ResearchContract):
    scaffold_id: Identifier
    predicted_independence_gain: StrictFloat
    uncertainty: Annotated[StrictFloat, Field(ge=0.0)]
    propensity: Probability


class ScaffoldDecisionContract(ResearchContract):
    decision_id: UUID
    episode_id: UUID
    feature_schema_version: Version
    context_snapshot_id: UUID
    candidates: tuple[ScaffoldCandidateContract, ...] = Field(min_length=1, max_length=64)
    predictions: tuple[ScaffoldPredictionContract, ...] = Field(min_length=1, max_length=64)
    selected_scaffold_id: Identifier
    policy_version: Version
    experiment_mode: ExperimentMode
    exploration: StrictBool
    randomization_token: Identifier | None
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        eligible = {candidate.scaffold_id for candidate in self.candidates if candidate.eligible}
        predicted = {prediction.scaffold_id for prediction in self.predictions}
        candidate_ids = {candidate.scaffold_id for candidate in self.candidates}
        if len(candidate_ids) != len(self.candidates):
            raise ValueError("candidate scaffold IDs must be unique")
        if len(predicted) != len(self.predictions) or predicted != eligible:
            raise ValueError("predictions must cover each eligible scaffold exactly once")
        if self.selected_scaffold_id not in eligible:
            raise ValueError("selected scaffold must be eligible")
        propensity_sum = sum(item.propensity for item in self.predictions)
        if abs(propensity_sum - 1.0) > 1e-9:
            raise ValueError("eligible scaffold propensities must sum to 1")
        if self.experiment_mode is ExperimentMode.BASELINE and self.exploration:
            raise ValueError("baseline decisions cannot explore")
        return self


class ScaffoldExposureContract(ResearchContract):
    exposure_id: UUID
    episode_id: UUID
    decision_id: UUID
    scaffold_id: Identifier
    scaffold_version: Version
    rendered_step_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=64)
    started_at: AwareDatetime
    completed_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_completion_time(self) -> Self:
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class SupportWithdrawalContract(ResearchContract):
    confirmation_id: UUID
    episode_id: UUID
    exposure_id: UUID
    all_support_removed: Literal[True]
    client_confirmed_at: AwareDatetime
    server_verified_at: AwareDatetime

    @model_validator(mode="after")
    def validate_confirmation_order(self) -> Self:
        if self.server_verified_at < self.client_confirmed_at:
            raise ValueError("server verification cannot precede client confirmation")
        return self


class ScoreComponentContract(ResearchContract):
    presentation_id: UUID
    score: NonNegativeScore
    maximum_score: Annotated[StrictFloat, Field(gt=0.0)]
    scoring_version: Version
    assistance_state: AssistanceState

    @model_validator(mode="after")
    def validate_component(self) -> Self:
        if self.score > self.maximum_score:
            raise ValueError("score cannot exceed maximum_score")
        if self.assistance_state is not AssistanceState.NONE:
            raise ValueError("Independence Gain components must be unsupported")
        return self


class IndependenceGainResultContract(ResearchContract):
    result_id: UUID
    episode_id: UUID
    decision_id: UUID
    unsupported_before: tuple[ScoreComponentContract, ...] = Field(min_length=1, max_length=32)
    unsupported_after: tuple[ScoreComponentContract, ...] = Field(min_length=1, max_length=32)
    raw_independence_gain: StrictFloat | None
    valid: StrictBool
    exclusion_reasons: tuple[Identifier, ...] = Field(max_length=32)
    formula_version: Literal[RAW_IG_FORMULA_VERSION]
    equivalence_version: Version
    support_withdrawal_confirmation_id: UUID
    server_authoritative: Literal[True]
    calculated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_raw_gain(self) -> Self:
        if self.valid:
            if self.exclusion_reasons:
                raise ValueError("valid IG cannot have exclusion reasons")
            before = sum(item.score for item in self.unsupported_before) / sum(
                item.maximum_score for item in self.unsupported_before
            )
            after = sum(item.score for item in self.unsupported_after) / sum(
                item.maximum_score for item in self.unsupported_after
            )
            expected = after - before
            if self.raw_independence_gain is None:
                raise ValueError("valid IG requires raw_independence_gain")
            if abs(self.raw_independence_gain - expected) > 1e-9:
                raise ValueError("raw_independence_gain must equal unsupported_after - unsupported_before")
        else:
            if not self.exclusion_reasons:
                raise ValueError("invalid IG requires an exclusion reason")
            if self.raw_independence_gain is not None:
                raise ValueError("invalid IG cannot authorize a numeric reward")
        return self


class PolicyUpdateAuthorizationContract(ResearchContract):
    authorization_id: UUID
    episode_id: UUID
    decision_id: UUID
    independence_gain_result_id: UUID
    experiment_mode: ExperimentMode
    valid_model3_result: StrictBool
    authorized: StrictBool
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def validate_authorization(self) -> Self:
        can_update = self.experiment_mode is ExperimentMode.PROPOSED and self.valid_model3_result
        if self.authorized != can_update:
            raise ValueError("policy update authorization requires proposed mode and valid Model 3 IG")
        return self


class BaselinePolicyContract(ResearchContract):
    policy_version: Version
    experiment_mode: Literal[ExperimentMode.BASELINE]
    selection_kind: Literal["fixed", "rule_based"]
    fixed_scaffold_id: Identifier | None
    rule_version: Version | None
    consumes_misconception_beliefs: Literal[False]
    learns_from_independence_gain: Literal[False]

    @model_validator(mode="after")
    def validate_policy_shape(self) -> Self:
        if self.selection_kind == "fixed" and self.fixed_scaffold_id is None:
            raise ValueError("fixed baseline policy requires fixed_scaffold_id")
        if self.selection_kind == "rule_based" and self.rule_version is None:
            raise ValueError("rule-based baseline policy requires rule_version")
        return self


class ExperimentAssignmentContract(ResearchContract):
    assignment_id: UUID
    learner_id: UUID
    experiment_id: Identifier
    experiment_version: Version
    mode: ExperimentMode
    assignment_method: Identifier
    assignment_token: Identifier
    assigned_at: AwareDatetime


class ProbeReservationContract(ResearchContract):
    reservation_id: UUID
    episode_id: UUID
    item_revision_id: Identifier
    parallel_family_id: Identifier
    measurement_role: Literal[MeasurementRole.UNSUPPORTED_BEFORE, MeasurementRole.UNSUPPORTED_AFTER]
    reservation_version: Version
    reserved_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if self.expires_at <= self.reserved_at:
            raise ValueError("probe reservation must expire after it is created")
        return self


_EVENT_PAYLOAD_RULES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "item_opened": (
        frozenset({"item_revision_id", "measurement_role"}),
        frozenset({"item_revision_id", "measurement_role"}),
    ),
    "answer_submitted": (
        frozenset({"attempt_id", "response_digest"}),
        frozenset({"attempt_id", "response_digest"}),
    ),
    "support_withdrawn": (
        frozenset({"withdrawal_confirmation_id"}),
        frozenset({"withdrawal_confirmation_id"}),
    ),
    "probe_started": (
        frozenset({"reservation_id"}),
        frozenset({"reservation_id"}),
    ),
    "session_interrupted": (
        frozenset({"reason_code"}),
        frozenset({"reason_code"}),
    ),
}
_PII_KEYS = frozenset(
    {"name", "full_name", "email", "phone", "address", "guardian_name", "raw_free_text"}
)


class EventEnvelopeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[EVENT_SCHEMA_VERSION]
    payload_schema_version: Version
    event_id: UUID
    learner_id: UUID
    session_id: UUID
    episode_id: UUID
    presentation_id: UUID | None
    sequence: SequenceNumber
    client_occurred_at: AwareDatetime
    server_received_at: AwareDatetime
    offline_batch_id: UUID | None
    event_type: Literal[
        "item_opened",
        "answer_submitted",
        "support_withdrawn",
        "probe_started",
        "session_interrupted",
    ]
    payload: dict[Identifier, Any] = Field(max_length=16)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        keys = set(self.payload)
        if keys & _PII_KEYS:
            raise ValueError("event payload contains prohibited personal or free-text data")
        required, allowed = _EVENT_PAYLOAD_RULES[self.event_type]
        if not required <= keys:
            raise ValueError(f"{self.event_type} payload is missing required fields")
        if not keys <= allowed:
            raise ValueError(f"{self.event_type} payload contains unsupported fields")
        for value in self.payload.values():
            if not isinstance(value, (str, int, float, bool, UUID)):
                # Pydantic converts ValueError, not TypeError, into a boundary ValidationError.
                raise ValueError(  # noqa: TRY004
                    "event payload values must be bounded scalar identifiers"
                )
        return self


class ParticipationRewardContract(ResearchContract):
    reward_id: UUID
    learner_id: UUID
    episode_id: UUID
    reward_type: Identifier
    amount: NonNegativeInt
    academic_mastery_evidence: Literal[False]
    awarded_at: AwareDatetime


class IndependentEvidenceContract(ResearchContract):
    """Unsupported academic evidence; deliberately separate from participation rewards."""

    evidence_id: UUID
    learner_id: UUID
    skill_id: Identifier
    presentation_id: UUID
    score_result_id: UUID
    measurement_role: Literal[
        MeasurementRole.UNSUPPORTED_BEFORE,
        MeasurementRole.UNSUPPORTED_AFTER,
        MeasurementRole.RETENTION,
    ]
    assistance_state: Literal[AssistanceState.NONE]
    evidence_version: Version
    recorded_at: AwareDatetime
