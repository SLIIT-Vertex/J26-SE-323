"""The attempt penalty fed to the knowledge model. One function, used everywhere.

Digital answers carry the child's real hints and time:

    0.6 * min(hints / 3, 1) + 0.4 * min(time_ms / 180000, 1)

Paper answers have no per-question time or hints, so they get a constant from the feature spec.
"""

DIGITAL = 1
PAPER = 0

HINT_WEIGHT = 0.6
HINT_CAP = 3
TIME_WEIGHT = 0.4
TIME_CAP_MS = 180_000
DEFAULT_TIME_MS = 12_000  # used when a digital answer has no time

# Must equal feature_spec.json -> penalty.digital_formula (a test enforces this).
DIGITAL_FORMULA = "0.6*min(hints/3,1) + 0.4*min(time_ms/180000,1)"


def compute_penalty(
    source: int,
    time_ms: int | None,
    hints: int | None,
    paper_penalty: float,
) -> float:
    if source == PAPER:
        return paper_penalty
    if source != DIGITAL:
        raise ValueError(f"source must be 0 (paper) or 1 (digital), got {source!r}")
    if time_ms is not None and time_ms < 0:
        raise ValueError("time_ms cannot be negative")
    if hints is not None and hints < 0:
        raise ValueError("hints cannot be negative")

    hint_part = min((hints or 0) / HINT_CAP, 1.0)
    time_part = min((DEFAULT_TIME_MS if time_ms is None else time_ms) / TIME_CAP_MS, 1.0)
    return HINT_WEIGHT * hint_part + TIME_WEIGHT * time_part
