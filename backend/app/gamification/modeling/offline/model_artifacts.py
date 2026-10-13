"""Offline-facing exports for model-neutral artifact lifecycle controls."""

from app.gamification.modeling.shared.artifact_registry import (
    ApprovalGatedArtifactRegistry,
    ModelArtifactBundle,
    model_card,
)

__all__ = ["ApprovalGatedArtifactRegistry", "ModelArtifactBundle", "model_card"]
