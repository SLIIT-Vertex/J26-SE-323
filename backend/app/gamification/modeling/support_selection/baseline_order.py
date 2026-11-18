"""The baseline condition's help order: the subject's fixed order, never learned.

The comparison group gets the subject's fixed order restricted to the helps the area offers and
can draw. It reads no history, no Model 1 reason and no Learning State, so nothing a child does
changes it. The record keeps the exact shape baseline episodes have always stored.

Mathematics (``MATHEMATICS_ORDER``) starts with the lightest cue on the child's own task and only
then changes the task, because help that leaves the child generating the answer transfers best to
an item with no help at all:

- ``visual_guidance``: the child still does all the reasoning; only the structure is shown.
- ``step_by_step_guidance``: short questions narrow the reasoning; the child still answers.
- ``conceptual_reexplanation``: the idea is said again from another angle, for a child whose cues
  did not land because the idea itself is not yet in place.
- ``simpler_same_game``: the same skill with easier quantities, so the child can succeed on the
  same structure and then return to the failed difficulty.
- ``prerequisite_repair``: leaves the skill for an earlier one. It costs the most time and its
  transfer is indirect, so it comes after every same-skill route.
- ``worked_parallel_example``: a full solution of a different problem. It is the most
  answer-adjacent and the most passive, so it is the last resort before withdrawal.

English (``ENGLISH_ORDER``) moves the simpler version up to second. The English games ask the
child to retrieve a word's meaning and link it among several look-alike choices. When the picture
cue has not worked, the load of the choices is usually what is in the way, and a successful link
with fewer choices is the same retrieval the fresh item will ask for. Guided questions and a
re-explanation of the meaning follow; prerequisite repair and the worked example stay last for the
same reasons as in Mathematics.

Sinhala packages deliver their three help types in the authored order (``SINHALA_ORDER``).

Types the area does not list, or that this episode cannot render, are skipped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.gamification.content.support_types import SUPPORT_TYPES, SupportType

MATHEMATICS_ORDER: tuple[SupportType, ...] = (
    "visual_guidance",
    "step_by_step_guidance",
    "conceptual_reexplanation",
    "simpler_same_game",
    "prerequisite_repair",
    "worked_parallel_example",
)
ENGLISH_ORDER: tuple[SupportType, ...] = (
    "visual_guidance",
    "simpler_same_game",
    "step_by_step_guidance",
    "conceptual_reexplanation",
    "prerequisite_repair",
    "worked_parallel_example",
)
assert set(MATHEMATICS_ORDER) == set(ENGLISH_ORDER) == set(SUPPORT_TYPES)
SINHALA_ORDER: tuple[SupportType, ...] = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
SUBJECT_ORDERS: dict[str, tuple[SupportType, ...]] = {
    "MAT": MATHEMATICS_ORDER,
    "ENG": ENGLISH_ORDER,
    "SIN": SINHALA_ORDER,
}


def subject_of(area_id: str) -> str:
    """The subject code in a Grade 5 area id, such as ``MAT`` in ``G5-AREA-MAT-01``."""

    return area_id.split("-")[2]


# The order policy version baseline records have always carried; it never changes with Model 2.
BASELINE_RECORD_VERSION = "support-order-v3"
BASELINE_FIXED_ORDER = "baseline_fixed_order"


@dataclass(frozen=True)
class BaselineOrder:
    order: tuple[str, ...]

    @property
    def first(self) -> str:
        return self.order[0]

    def as_record(self) -> dict[str, object]:
        return {
            "order_policy_version": BASELINE_RECORD_VERSION,
            "learning_state_input": {"status": "not_available", "reason": "NOT_FOUND"},
            "history_by_learning_state": {},
            "support_order": list(self.order),
            "selected_action": self.first,
            "reason_family": None,
            "support_selection_mode": BASELINE_FIXED_ORDER,
            "learner_activity_support_preference": {
                "basis": "valid_unsupported_after_outcomes",
                "supported_correctness_used": False,
                "preferred_support": None,
                "by_support": {},
            },
        }


def fixed_order(subject: str, eligible: Iterable[str], renderable: Iterable[str]) -> tuple[str, ...]:
    """The subject's fixed order restricted to the helps this area offers and can draw.

    Raises ``ValueError("NO_RENDERABLE_SUPPORT")`` when none can be drawn.
    """

    offered, drawable = set(eligible), set(renderable)
    order = tuple(
        support for support in SUBJECT_ORDERS[subject] if support in offered and support in drawable
    )
    if not order:
        raise ValueError("NO_RENDERABLE_SUPPORT")
    return order


def baseline_order(subject: str, eligible: Iterable[str], renderable: Iterable[str]) -> BaselineOrder:
    return BaselineOrder(fixed_order(subject, eligible, renderable))
