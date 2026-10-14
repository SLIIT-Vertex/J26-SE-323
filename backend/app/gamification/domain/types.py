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
    BASELINE_STARTED = "baseline_started"
    BASELINE_RECORDED = "baseline_recorded"
    STRUGGLE_ASSESSED = "struggle_assessed"
    MISCONCEPTION_RECORDED = "misconception_recorded"
    SUPPORT_DECIDED = "support_decided"
    SUPPORT_DELIVERED = "support_delivered"
    SUPPORT_WITHDRAWN = "support_withdrawn"
    VERIFICATION_SCHEDULED = "verification_scheduled"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_RECORDED = "verification_recorded"
    OUTCOME_RECORDED = "outcome_recorded"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    INVALIDATED = "invalidated"

    @property
    def is_terminal(self) -> bool:
        return self in {
            EpisodePhase.COMPLETED,
            EpisodePhase.ABANDONED,
            EpisodePhase.INVALIDATED,
        }


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

