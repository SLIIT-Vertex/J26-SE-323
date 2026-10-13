"""Public offline dataset, evaluation, artifact, and command interfaces."""

from app.gamification.modeling.misconception_inference.evaluation import (
    ClassificationEvaluation,
    evaluate_classification,
)
from app.gamification.modeling.misconception_inference.training import (
    train_frequency_candidate,
)
from app.gamification.modeling.offline.dataset_manifest import DatasetManifest, DatasetRow
from app.gamification.modeling.shared.artifact_registry import (
    ApprovalGatedArtifactRegistry,
    ModelArtifactBundle,
)
from app.gamification.modeling.support_selection.evaluation import (
    PolicyEvaluation,
    evaluate_logged_policy,
)
DEFAULT_PROTOTYPE_STATUS = "TODO_EXPERT_AUTHORIZATION_AND_REVIEW"


def load_default_prototype_rows() -> list[DatasetRow]:
    """Compatibility export; new code should import from `synthetic.datasets`."""

    from app.gamification.modeling.synthetic.datasets import load_default_prototype_rows

    return load_default_prototype_rows()


def load_fake_expert_reviews() -> dict[str, object]:
    """Compatibility export; new code should import from `synthetic.datasets`."""

    from app.gamification.modeling.synthetic.datasets import load_fake_expert_reviews

    return load_fake_expert_reviews()

__all__ = [
    "DEFAULT_PROTOTYPE_STATUS",
    "ApprovalGatedArtifactRegistry",
    "ClassificationEvaluation",
    "DatasetManifest",
    "DatasetRow",
    "ModelArtifactBundle",
    "PolicyEvaluation",
    "evaluate_classification",
    "evaluate_logged_policy",
    "load_default_prototype_rows",
    "load_fake_expert_reviews",
    "train_frequency_candidate",
]
