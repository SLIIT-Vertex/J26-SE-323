from typing import Annotated, Literal, Self
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
    DecisionMode,
    EpisodePhase,
    EvidenceSupportState,
    OutcomeValidity,
    SupportActionType,
)

BOUNDARY_CONTRACT_VERSION = "gamification-boundary-v1"

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
ContractVersion = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9-]*-v[1-9][0-9]*$", strict=True),
]
Probability = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
NonNegativeMilliseconds = Annotated[StrictInt, Field(ge=0, le=86_400_000)]
Language = Literal["si", "ta", "en"]


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EpisodeStateContract(BoundaryModel):
    contract_version: ContractVersion
    episode_id: UUID
    learner_id: UUID
    skill_id: Identifier
    protocol_version: Version
    phase: EpisodePhase
    created_at: AwareDatetime
    transitioned_at: AwareDatetime
    terminal_reason: Identifier | None = None

    @model_validator(mode="after")
    def validate_terminal_state(self) -> Self:
        if self.transitioned_at < self.created_at:
            raise ValueError("transitioned_at cannot precede created_at")
        early_terminal = self.phase in {EpisodePhase.ABANDONED, EpisodePhase.INVALIDATED}
        if early_terminal and self.terminal_reason is None:
            raise ValueError("abandoned and invalidated episodes require a terminal reason")
        if not early_terminal and self.terminal_reason is not None:
            raise ValueError("terminal reason is only valid for abandoned or invalidated episodes")
        return self


class SkillMasterySnapshot(BoundaryModel):
    contract_version: ContractVersion
    learner_id: UUID
    skill_id: Identifier
    skill_taxonomy_version: Version
    mastery_probability: Probability
    uncertainty: Probability
    model_version: Version
    observed_at: AwareDatetime


class AttemptSubmission(BoundaryModel):
    contract_version: ContractVersion
    attempt_id: UUID
    learner_id: UUID
    item_id: Identifier
    item_version: Version
    skill_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=8)
    skill_taxonomy_version: Version
    language: Language
    correct: StrictBool
    score: Probability
    response_time_ms: NonNegativeMilliseconds | None
    support_exposure: Literal["none", "supported", "unknown"]
    attempted_at: AwareDatetime


class LearnerStateSnapshot(BoundaryModel):
    contract_version: ContractVersion
    learner_id: UUID
    support_need: Probability
    confidence: Probability
    reliability: Probability
    observed_at: AwareDatetime
    source_version: Version


class MisconceptionBelief(BoundaryModel):
    misconception_id: Identifier
    probability: Probability


class SupportAssetRequestContract(BoundaryModel):
    contract_version: ContractVersion
    learner_id: UUID
    skill_id: Identifier
    skill_taxonomy_version: Version
    action_type: SupportActionType
    misconception_catalogue_version: Version
    beliefs: tuple[MisconceptionBelief, ...] = Field(min_length=1, max_length=128)
    approved_evidence_ids: tuple[Identifier, ...] = Field(max_length=32)
    prohibited_content: tuple[Identifier, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_beliefs(self) -> Self:
        identifiers = [belief.misconception_id for belief in self.beliefs]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("misconception identifiers must be unique")
        if abs(sum(belief.probability for belief in self.beliefs) - 1.0) > 1e-9:
            raise ValueError("misconception probabilities must sum to 1")
        return self


class SupportAssetResponseContract(BoundaryModel):
    contract_version: ContractVersion
    support_asset_id: Identifier
    content_version: Version
    verified: StrictBool
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)


class ConsentDecisionContract(BoundaryModel):
    contract_version: ContractVersion
    learner_id: UUID
    purpose: Identifier
    granted: StrictBool
    consent_version: Version
    decided_at: AwareDatetime
    expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.decided_at:
            raise ValueError("expires_at must be later than decided_at")
        return self


class ModelArtifactContract(BoundaryModel):
    contract_version: ContractVersion
    model_id: Identifier
    model_version: Version
    artifact_digest: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    approved: StrictBool
    registered_at: AwareDatetime


FeatureValue = StrictFloat | StrictInt | StrictBool | Identifier | None


class FeatureSnapshotContract(BoundaryModel):
    contract_version: ContractVersion
    snapshot_id: UUID
    learner_id: UUID
    skill_id: Identifier
    captured_at: AwareDatetime
    protocol_version: Version
    taxonomy_version: Version
    feature_definition_version: Version
    values: dict[Identifier, FeatureValue] = Field(max_length=256)


class PolicyCandidateContract(BoundaryModel):
    action_id: Identifier
    action_type: SupportActionType
    propensity: Probability
    eligible: StrictBool
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)


class PolicyDecisionContract(BoundaryModel):
    contract_version: ContractVersion
    decision_id: UUID
    feature_snapshot_id: UUID
    selected_action_id: Identifier
    mode: DecisionMode
    policy_version: Version
    support_catalogue_version: Version
    candidates: tuple[PolicyCandidateContract, ...] = Field(min_length=1, max_length=64)
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def validate_candidates(self) -> Self:
        identifiers = [candidate.action_id for candidate in self.candidates]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("candidate action identifiers must be unique")
        eligible = [candidate for candidate in self.candidates if candidate.eligible]
        if not eligible:
            raise ValueError("at least one candidate must be eligible")
        if any(candidate.propensity != 0.0 for candidate in self.candidates if not candidate.eligible):
            raise ValueError("ineligible candidates must have zero propensity")
        if abs(sum(candidate.propensity for candidate in eligible) - 1.0) > 1e-9:
            raise ValueError("eligible candidate propensities must sum to 1")
        if self.selected_action_id not in {candidate.action_id for candidate in eligible}:
            raise ValueError("selected action must be an eligible candidate")
        return self


class IndependenceOutcomeContract(BoundaryModel):
    contract_version: ContractVersion
    outcome_id: UUID
    episode_id: UUID
    validity: OutcomeValidity
    formula_version: Version
    baseline_support_state: EvidenceSupportState
    verification_support_state: EvidenceSupportState
    independence_gain: StrictFloat | None = None
    invalid_reason: Identifier | None = None
    recorded_at: AwareDatetime

    @model_validator(mode="after")
    def validate_research_eligibility(self) -> Self:
        if self.validity is OutcomeValidity.VALID:
            if (
                self.baseline_support_state is not EvidenceSupportState.UNSUPPORTED
                or self.verification_support_state is not EvidenceSupportState.UNSUPPORTED
            ):
                raise ValueError("valid outcomes require unsupported baseline and verification")
            if self.independence_gain is None:
                raise ValueError("valid outcomes require independence_gain")
            if self.invalid_reason is not None:
                raise ValueError("valid outcomes cannot include invalid_reason")
        elif self.validity is OutcomeValidity.INVALID:
            if self.invalid_reason is None:
                raise ValueError("invalid outcomes require invalid_reason")
            if self.independence_gain is not None:
                raise ValueError("invalid outcomes cannot include independence_gain")
        elif self.independence_gain is not None or self.invalid_reason is not None:
            raise ValueError("pending outcomes cannot include a result or invalid reason")
        return self


class CurriculumEvidenceContract(BoundaryModel):
    contract_version: ContractVersion
    evidence_id: Identifier
    skill_id: Identifier
    skill_taxonomy_version: Version
    source_version: Version
    content_hash: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    approved: StrictBool
    language: Language


class AuditEventContract(BoundaryModel):
    contract_version: ContractVersion
    event_id: UUID
    event_type: Identifier
    subject_id: Identifier
    occurred_at: AwareDatetime
    reason_codes: tuple[Identifier, ...] = Field(min_length=1, max_length=32)
    metadata: dict[Identifier, StrictFloat | StrictInt | StrictBool | Identifier | None] = Field(
        max_length=64
    )

