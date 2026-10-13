import math
from typing import Mapping

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.misconception_inference.contracts import (
    MISCONCEPTION_MODEL_VERSION,
    UNKNOWN_CODE,
)
from app.gamification.modeling.shared.contracts import MisconceptionDistribution


class ProbabilisticMisconceptionModel:
    """Transparent authored log-linear candidate used for engineering validation."""

    def __init__(
        self,
        *,
        catalogue_version: str,
        error_likelihoods: Mapping[str, Mapping[str, float]],
        class_priors: Mapping[str, float],
        abstain_threshold: float = 0.6,
    ) -> None:
        if not 0 < abstain_threshold <= 1:
            raise ValueError("abstain_threshold must be in (0, 1]")
        classes = set(class_priors) | {UNKNOWN_CODE}
        if any(value <= 0 for value in class_priors.values()):
            raise ValueError("class priors must be positive")
        self.catalogue_version = catalogue_version
        self.error_likelihoods = {
            error: dict(weights) for error, weights in error_likelihoods.items()
        }
        self.class_priors = {
            code: class_priors.get(code, 0.05) for code in sorted(classes)
        }
        self.abstain_threshold = abstain_threshold

    def predict(self, snapshot: FeatureSnapshotRecord) -> MisconceptionDistribution:
        error_code = str(snapshot.values.get("structured_error_code") or "")
        likelihoods = self.error_likelihoods.get(error_code, {})
        logits = {
            code: math.log(prior) + likelihoods.get(code, 0.0)
            for code, prior in self.class_priors.items()
        }
        peak = max(logits.values())
        exponentials = {code: math.exp(value - peak) for code, value in logits.items()}
        total = sum(exponentials.values())
        probabilities = {code: value / total for code, value in exponentials.items()}
        reasons = ("ERROR_PATTERN_MATCHED",) if likelihoods else ("SPARSE_OR_UNSEEN_SKILL",)
        return build_distribution(
            probabilities,
            model_version=MISCONCEPTION_MODEL_VERSION,
            catalogue_version=self.catalogue_version,
            abstain_threshold=self.abstain_threshold,
            reasons=reasons,
        )


def build_distribution(
    probabilities: Mapping[str, float],
    *,
    model_version: str,
    catalogue_version: str,
    abstain_threshold: float,
    reasons: tuple[str, ...],
) -> MisconceptionDistribution:
    """Normalize shared output metadata without binding consumers to an implementation."""

    normalized = dict(probabilities)
    confidence = max(normalized.values())
    abstained = confidence < abstain_threshold or max(
        normalized, key=normalized.__getitem__
    ) == UNKNOWN_CODE
    if abstained:
        reasons += ("ABSTAIN_LOW_CONFIDENCE",)
    entropy = -sum(value * math.log(value) for value in normalized.values() if value > 0)
    return MisconceptionDistribution(
        probabilities=normalized,
        entropy=entropy,
        confidence=confidence,
        abstained=abstained,
        model_version=model_version,
        catalogue_version=catalogue_version,
        reason_codes=reasons,
    )
