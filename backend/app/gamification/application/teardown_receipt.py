"""The phone's revision-bound support-teardown receipt.

A flow that verifies teardown (``accepts_teardown_receipt``) withdraws help only when the phone
reports, for the exact support and manifest revisions, that nothing of the help remains in the
game scene, the DOM, the listeners, the live region or the cached solution.
"""

from __future__ import annotations

from collections.abc import Mapping

TEARDOWN_RECEIPT_VERSION = "pillam-teardown-receipt-v1"
ZERO_COUNTS = ("phaser_support_objects_remaining", "dom_support_nodes_remaining", "listeners_remaining")
TRUE_FLAGS = ("live_region_cleared", "cached_solution_cleared")


def simulated_receipt(support_revision_id: str, manifest_revision_id: str) -> dict[str, object]:
    """A receipt for synthetic clients (seeding, simulated cohorts). It is marked as simulated so
    no audit can mistake it for a phone's observation."""

    return {
        "receipt_version": TEARDOWN_RECEIPT_VERSION,
        "support_revision_id": support_revision_id,
        "manifest_revision_id": manifest_revision_id,
        **dict.fromkeys(ZERO_COUNTS, 0),
        **dict.fromkeys(TRUE_FLAGS, True),
        "source": "simulated_client",
    }


def supported_summary(flow: object) -> dict[str, object]:
    """What a synthetic client reports for one supported attempt: one move where the flow
    requires the child to act (guided help), nothing where the flow takes no summary."""

    return {"move_count": 1} if getattr(flow, "accepts_teardown_receipt", False) else {}


def shown_steps(response: Mapping[str, object]) -> int:
    """How many steps a synthetic client pressed through: every step of the shown example."""

    support = response.get("support")
    manifest = support.get("game_manifest") if isinstance(support, Mapping) else None
    worked = manifest.get("worked_example") if isinstance(manifest, Mapping) else None
    steps = worked.get("steps_si") if isinstance(worked, Mapping) else None
    return max(1, min(8, len(steps))) if isinstance(steps, list) else 3
