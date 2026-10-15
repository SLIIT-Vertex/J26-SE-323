from typing import Protocol

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

MISCONCEPTION_MODEL_VERSION = "probabilistic-authored-v1"
UNKNOWN_CODE = "unknown/other"


class MisconceptionPredictor(Protocol):
    """Capability required by orchestration, independent of model implementation."""

    def predict(self, snapshot: FeatureSnapshotRecord) -> MisconceptionDistribution: ...
