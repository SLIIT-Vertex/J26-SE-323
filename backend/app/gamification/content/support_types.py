"""The one contract for help types a game may deliver.

Every flow, the learning-flow response, and the generated phone types read the help types from
here. A flow never declares its own string union.
"""

from __future__ import annotations

from typing import Literal, get_args

SupportType = Literal[
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
    "simpler_same_game",
    "prerequisite_repair",
    "conceptual_reexplanation",
]
# Canonical order: the three original game types first, so their relative order stays the one
# earlier catalogue rows were validated against.
SUPPORT_TYPES: tuple[SupportType, ...] = get_args(SupportType)
ORIGINAL_GAME_SUPPORT_TYPES: tuple[SupportType, ...] = SUPPORT_TYPES[:3]

EnglishTagKey = Literal[
    "VISUAL_GUIDANCE",
    "GUIDED_REASONING",
    "WORKED_EXAMPLE",
    "SIMPLER_VERSION",
    "PREREQUISITE_REPAIR",
    "CONCEPTUAL_REEXPLANATION",
]
ENGLISH_TAG_KEYS: dict[SupportType, EnglishTagKey] = {
    "visual_guidance": "VISUAL_GUIDANCE",
    "step_by_step_guidance": "GUIDED_REASONING",
    "worked_parallel_example": "WORKED_EXAMPLE",
    "simpler_same_game": "SIMPLER_VERSION",
    "prerequisite_repair": "PREREQUISITE_REPAIR",
    "conceptual_reexplanation": "CONCEPTUAL_REEXPLANATION",
}
# The small English tag shown on the phone's support screen, keyed by the tag key above.
ENGLISH_TAGS: dict[EnglishTagKey, str] = {
    "VISUAL_GUIDANCE": "Visual guidance",
    "GUIDED_REASONING": "Guided reasoning",
    "WORKED_EXAMPLE": "Worked example",
    "SIMPLER_VERSION": "Simpler version",
    "PREREQUISITE_REPAIR": "Prerequisite repair",
    "CONCEPTUAL_REEXPLANATION": "Conceptual re-explanation",
}

assert set(ENGLISH_TAG_KEYS) == set(SUPPORT_TYPES)
assert set(ENGLISH_TAGS) == set(get_args(EnglishTagKey))
