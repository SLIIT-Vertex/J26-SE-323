from collections.abc import Mapping

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.misconception_inference.contracts import UNKNOWN_CODE
from app.gamification.modeling.misconception_inference.probabilistic_model import (
    build_distribution,
)
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

DETERMINISTIC_BASELINE_VERSION = "deterministic-error-map-v1"


class DeterministicMisconceptionBaseline:
    """Map authored error codes to deterministic misconception beliefs."""

    def __init__(
        self, error_map: Mapping[str, str], *, catalogue_version: str | None = None
    ) -> None:
        self._error_map = dict(error_map)
        self._catalogue_version = catalogue_version

    def predict(
        self, snapshot: FeatureSnapshotRecord, *, catalogue_version: str | None = None
    ) -> MisconceptionDistribution:
        resolved_catalogue_version = catalogue_version or self._catalogue_version
        if not resolved_catalogue_version:
            raise ValueError("catalogue_version is required")
        error_code = snapshot.values.get("structured_error_code")
        prediction = self._error_map.get(str(error_code), UNKNOWN_CODE)
        return build_distribution(
            {prediction: 1.0},
            model_version=DETERMINISTIC_BASELINE_VERSION,
            catalogue_version=resolved_catalogue_version,
            abstain_threshold=0.0,
            reasons=("AUTHORED_ERROR_MAPPING",) if prediction != UNKNOWN_CODE else ("NO_MAPPING",),
        )
