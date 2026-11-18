"""The baseline condition's help order: the subject's fixed order, never learned.

The comparison group gets the subject's fixed order restricted to the helps the area offers and
can draw. It reads no history, no Model 1 reason and no Learning State, so nothing a child does
changes it. The record keeps the exact shape baseline episodes have always stored.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.gamification.modeling.support_selection.support_order import SUBJECT_ORDERS

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
