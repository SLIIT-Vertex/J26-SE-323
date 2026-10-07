from enum import StrEnum


class AssistanceLevel(StrEnum):
    INDEPENDENT_RETRY = "L0"
    METACOGNITIVE_PROMPT = "L1"
    CONCEPTUAL_HINT = "L2"
    TARGETED_HINT = "L3"
    GUIDED_STEPS = "L4"
    SIMILAR_WORKED_EXAMPLE = "L5"
    FULL_EXPLANATION = "L6"
