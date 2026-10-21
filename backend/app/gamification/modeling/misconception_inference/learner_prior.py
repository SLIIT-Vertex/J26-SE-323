"""Bounded learner/skill Dirichlet prior, applied to authored likelihoods.

Only the last five completed, unsupported answers for this learner and skill can count.
The caller owns the scope and chronology; supported answers never enter the prior.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping

PRIOR_VERSION = "learner-prior-v1"
PRIOR_CAP = 5


def prior_errors(history: Iterable[Mapping[str, object]]) -> list[str]:
    errors = []
    for state in history:
        for attempt in state.get("attempts") or []:
            if (
                attempt.get("role") in {"unsupported_before", "unsupported_after"}
                and attempt.get("assistance_state", "none") == "none"
            ):
                # Correct answers still occupy a place in the five-answer window.
                errors.append(
                    str(attempt.get("structured_error_code")) if not attempt.get("correct") else ""
                )
    return errors[-PRIOR_CAP:]


def apply_learner_prior(belief: Mapping[str, object], errors: Iterable[str]) -> dict[str, object]:
    likelihood = {key: float(value) for key, value in belief["probabilities"].items()}
    recent = list(errors)[-PRIOR_CAP:]
    counts = Counter(error for error in recent if error in likelihood)
    weights = {key: value * (1 + counts[key]) for key, value in likelihood.items()}
    total = sum(weights.values())
    posterior = {key: value / total for key, value in weights.items()}
    ordered = sorted(posterior, key=posterior.get, reverse=True)
    top = ordered[0]
    confidence = posterior[top]
    low = confidence < 0.4 or (len(ordered) > 1 and confidence - posterior[ordered[1]] < 0.1)
    result = dict(belief)
    result.update(
        probabilities=posterior,
        posterior=posterior,
        likelihood=likelihood,
        prior_counts={key: counts[key] for key in likelihood},
        prior_version=PRIOR_VERSION,
        prior_pseudocount=1,
        prior_window=recent,
        prior_sample_size=len(recent),
        learner_prior_used=bool(counts),
        low_confidence=low,
        confidence=confidence,
        predicted_label=top,
        entropy=-sum(p * math.log(p) for p in posterior.values() if p > 0),
    )
    if "top_hypothesis" in result:
        result["top_hypothesis"] = top
    return result
