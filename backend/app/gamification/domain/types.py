from enum import StrEnum
from typing import NewType
from uuid import UUID

EpisodeId = NewType("EpisodeId", UUID)
SessionId = NewType("SessionId", UUID)
FeatureSnapshotId = NewType("FeatureSnapshotId", UUID)
PolicyDecisionId = NewType("PolicyDecisionId", UUID)
AuditEventId = NewType("AuditEventId", UUID)

SkillId = NewType("SkillId", str)
ItemId = NewType("ItemId", str)
ActionId = NewType("ActionId", str)
ModelId = NewType("ModelId", str)
ProtocolVersion = NewType("ProtocolVersion", str)
ContractVersion = NewType("ContractVersion", str)
TaxonomyVersion = NewType("TaxonomyVersion", str)
CatalogueVersion = NewType("CatalogueVersion", str)
ContentVersion = NewType("ContentVersion", str)


class EpisodePhase(StrEnum):
    CREATED = "created"
    BASELINE_RESERVED = "baseline_reserved"
    BASELINE_ACTIVE = "baseline_active"
    BASELINE_SCORED = "baseline_scored"
    GAMEPLAY_ACTIVE = "gameplay_active"
    DIFFICULTY_DETECTED = "difficulty_detected"
    MISCONCEPTION_ESTIMATED = "misconception_estimated"
    SUPPORT_DECIDED = "support_decided"
    SUPPORT_ACTIVE = "support_active"
    SUPPORTED_PRACTICE_COMPLETE = "supported_practice_complete"
    SUPPORT_WITHDRAWN = "support_withdrawn"
    INDEPENDENT_CHECK_ACTIVE = "independent_check_active"
    INDEPENDENT_CHECK_SCORED = "independent_check_scored"
    REWARD_VALIDATED = "reward_validated"
    POLICY_UPDATED = "policy_updated"
    COMPLETED = "completed"
    ABORTED = "aborted"
    INVALIDATED = "invalidated"

    # Source-compatibility aliases for the pre-canonical implementation. These aliases serialize
    # to the canonical values and are deliberately omitted when the enum is iterated.
    BASELINE_STARTED = BASELINE_ACTIVE
    BASELINE_RECORDED = BASELINE_SCORED
    STRUGGLE_ASSESSED = DIFFICULTY_DETECTED
    MISCONCEPTION_RECORDED = MISCONCEPTION_ESTIMATED
    SUPPORT_DELIVERED = SUPPORT_ACTIVE
    VERIFICATION_SCHEDULED = INDEPENDENT_CHECK_ACTIVE
    VERIFICATION_STARTED = INDEPENDENT_CHECK_ACTIVE
    VERIFICATION_RECORDED = INDEPENDENT_CHECK_SCORED
    OUTCOME_RECORDED = REWARD_VALIDATED
    ABANDONED = ABORTED

    @property
    def is_terminal(self) -> bool:
        return self in {
            EpisodePhase.COMPLETED,
            EpisodePhase.ABORTED,
            EpisodePhase.INVALIDATED,
        }


class MeasurementRole(StrEnum):
    """Server-assigned purpose of an item presentation."""

    PRACTICE = "practice"
    UNSUPPORTED_BEFORE = "unsupported_before"
    SUPPORTED_PRACTICE = "supported_practice"
    UNSUPPORTED_AFTER = "unsupported_after"
    RETENTION = "retention"


class AssistanceState(StrEnum):
    """Assistance known at presentation time; never inferred from a later screen name."""

    NONE = "none"
    SCAFFOLD_ACTIVE = "scaffold_active"
    TUTOR_ACTIVE = "tutor_active"
    ADULT_REPORTED = "adult_reported"
    UNKNOWN = "unknown"


class ExperimentMode(StrEnum):
    BASELINE = "baseline"
    PROPOSED = "proposed"


class SupportActionType(StrEnum):
    INDEPENDENT_RETRY = "independent_retry"
    METACOGNITIVE_PROMPT = "metacognitive_prompt"
    VISUAL_GUIDANCE = "visual_guidance"
    CONCEPTUAL_HINT = "conceptual_hint"
    TARGETED_HINT = "targeted_hint"
    GUIDED_STEPS = "guided_steps"
    SIMILAR_WORKED_EXAMPLE = "similar_worked_example"
    FULL_EXPLANATION = "full_explanation"


class DecisionMode(StrEnum):
    """How a support decision was produced.

    ``DETERMINISTIC_REFERENCE`` is a deprecated alias of ``PERFORMANCE_TRIGGERED_FIXED``
    (CF-13). Callers may still send the alias; new logs should use the canonical mode.
    """

    PERFORMANCE_TRIGGERED_FIXED = "performance_triggered_fixed"
    DETERMINISTIC_REFERENCE = "deterministic_reference"
    SHADOW = "shadow"
    LEARNED = "learned"
    CONSERVATIVE_FALLBACK = "conservative_fallback"


class OutcomeValidity(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class EvidenceSupportState(StrEnum):
    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"
    UNKNOWN = "unknown"

