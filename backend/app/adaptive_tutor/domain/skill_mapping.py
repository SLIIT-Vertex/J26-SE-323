from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class SkillNode:
    domain_tag: str
    skill_id: str
    name: str
    sinhala_designation: str
    description: str

    @property
    def retrieval_text(self) -> str:
        return (
            f"{self.skill_id}. {self.name}. Sinhala: {self.sinhala_designation}. "
            f"Domain: {self.domain_tag}. {self.description}"
        )


class ConversationRole(StrEnum):
    LEARNER = "LEARNER"
    TUTOR = "TUTOR"


class LearningIntent(StrEnum):
    EXPLANATION_REQUEST = "EXPLANATION_REQUEST"
    HINT_REQUEST = "HINT_REQUEST"
    FOLLOW_UP_QUESTION = "FOLLOW_UP_QUESTION"
    ANSWER_SUBMISSION = "ANSWER_SUBMISSION"
    ANOTHER_EXAMPLE_REQUEST = "ANOTHER_EXAMPLE_REQUEST"
    GREETING = "GREETING"
    OFF_TOPIC = "OFF_TOPIC"


class SkillMappingStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"
    NOT_SKILL_RELATED = "NOT_SKILL_RELATED"


class SkillMappingReasonCode(StrEnum):
    DIRECT_SKILL_EVIDENCE = "DIRECT_SKILL_EVIDENCE"
    CONVERSATION_CONTEXT_USED = "CONVERSATION_CONTEXT_USED"
    ACTIVE_SKILL_USED = "ACTIVE_SKILL_USED"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUTSIDE_SUPPORTED_TAXONOMY = "OUTSIDE_SUPPORTED_TAXONOMY"
    NOT_SKILL_RELATED = "NOT_SKILL_RELATED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
