"""Model 3 for one adaptive-game episode: measured from the withdrawn item only.

The measurement reads the unsupported-before attempt and the fresh unsupported-after attempt.
It never reads the help rounds or any supported attempt, so help correctness cannot leak into
Independence Gain or into the Model 2 reward.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from uuid import uuid4

FORMULA_VERSION = "raw-independence-gain-v1"
_WITHDRAWAL_FLAGS = (
    "all_support_removed",
    "answer_revealing_state_cleared",
    "input_handlers_cleared",
)


def measure_withdrawn_episode(
    state: Mapping[str, object],
    *,
    after_item: Mapping[str, object],
    after_score: Mapping[str, object],
    scoring_version: str,
    measurement_version: str,
    equivalence_version: str,
    additional_exclusions: Iterable[str] = (),
) -> dict[str, object]:
    """Return the measurement record. ``raw_independence_gain`` is ``None`` when invalid."""

    attempts = state["attempts"]
    presentations = state["presentations"]
    assert isinstance(attempts, list) and isinstance(presentations, list)
    before = next(row for row in attempts if row["role"] == "unsupported_before")
    before_item = next(row for row in presentations if row["role"] == "unsupported_before")
    exclusions: list[str] = []
    exposure = state.get("scaffold_exposure")
    if not isinstance(exposure, Mapping) or not exposure.get("fully_withdrawn"):
        exclusions.append("SUPPORT_NOT_WITHDRAWN")
    withdrawal = state.get("withdrawal")
    if not isinstance(withdrawal, Mapping) or not all(
        withdrawal.get(flag) is True for flag in _WITHDRAWAL_FLAGS
    ):
        exclusions.append("WITHDRAWAL_NOT_VERIFIED")
    if (
        before.get("scoring_version") != scoring_version
        or after_score.get("scoring_version") != scoring_version
    ):
        exclusions.append("SCORING_VERSION_MISMATCH")
    if before.get("assistance_state") != "none" or after_score.get("assistance_state") != "none":
        exclusions.append("ASSISTANCE_CONTAMINATION")
    if after_item.get("role") != "unsupported_after":
        exclusions.append("AFTER_ITEM_NOT_UNSUPPORTED")
    if after_item.get("skill_id") != state.get("skill_id"):
        exclusions.append("SKILL_MISMATCH")
    if after_item["parallel_family_id"] != before_item["parallel_family_id"]:
        exclusions.append("INCOMPATIBLE_PARALLEL_FAMILY")
    if after_item["revision_id"] == before_item["revision_id"]:
        exclusions.append("AFTER_ITEM_NOT_FRESH")
    if after_item["revision_id"] in _support_revisions(state):
        exclusions.append("AFTER_ITEM_SEEN_DURING_SUPPORT")
    exclusions.extend(additional_exclusions)
    valid = not exclusions
    baseline = Decimal(str(before["earned_score"])) / Decimal(str(before["maximum_score"]))
    after = Decimal(str(after_score["earned_score"])) / Decimal(str(after_score["maximum_score"]))
    raw_ig = after - baseline if valid else None
    return {
        "measurement_id": str(uuid4()),
        "formula_version": FORMULA_VERSION,
        "measurement_version": measurement_version,
        "equivalence_version": equivalence_version,
        "scoring_version": scoring_version,
        "before_earned": before["earned_score"],
        "before_maximum": before["maximum_score"],
        "after_earned": after_score["earned_score"],
        "after_maximum": after_score["maximum_score"],
        "after_presentation_id": after_score["presentation_id"],
        "baseline": str(baseline),
        "after": str(after),
        "raw_independence_gain": None if raw_ig is None else str(raw_ig),
        "percentage_point_value": None if raw_ig is None else str(raw_ig * 100),
        "valid": valid,
        "exclusion_reasons": exclusions,
        "supported_correctness_used_as_reward": False,
    }


def _support_revisions(state: Mapping[str, object]) -> set[str]:
    loop = state.get("support_loop")
    if not isinstance(loop, Mapping):
        return set()
    revisions: set[str] = set()
    for round_record in loop.get("rounds", ()):  # type: ignore[union-attr]
        for stage in round_record.get("stages", ()):
            item = stage.get("item")
            if isinstance(item, Mapping):
                revisions.add(str(item["revision_id"]))
    return revisions
