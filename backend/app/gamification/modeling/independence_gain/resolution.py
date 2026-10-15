"""Post-verification change in posterior mass. This is an outcome, not a decision feature."""

from collections.abc import Mapping

RESOLUTION_FORMULA_VERSION = "posterior-mass-drop-v1"
# Same catalogue label as Model 1. This package does not import that model.
UNKNOWN_LABEL = "unknown/other"


def diagnosed_misconception(probabilities: Mapping[str, float]) -> str:
    ranked = sorted(
        (
            (code, probability)
            for code, probability in probabilities.items()
            if code != UNKNOWN_LABEL
        ),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        raise ValueError("no diagnosed misconception")
    return ranked[0][0]


def misconception_resolution(
    decision_probabilities: Mapping[str, float],
    post_verification_probabilities: Mapping[str, float],
    diagnosed_code: str | None = None,
) -> float:
    """Drop in posterior mass on the misconception diagnosed at the decision.

    Positive means that mass fell after the unsupported verification. The inputs are
    post-decision evidence and must not be written into a decision feature snapshot.
    """

    code = diagnosed_code or diagnosed_misconception(decision_probabilities)
    if code not in decision_probabilities or code not in post_verification_probabilities:
        raise ValueError("diagnosed misconception is missing from a posterior")
    return decision_probabilities[code] - post_verification_probabilities[code]
