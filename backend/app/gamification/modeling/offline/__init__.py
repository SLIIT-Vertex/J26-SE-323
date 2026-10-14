"""Public offline dataset, evaluation, artifact, and command interfaces."""

from app.gamification.modeling.misconception_inference.evaluation import (
    ClassificationEvaluation,
    evaluate_classification,
)
from app.gamification.modeling.misconception_inference.training import (
    train_frequency_candidate,
    train_likelihood_tables,
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


def load_fake_expert_review_simulation() -> dict[str, object]:
    """Compatibility export; new code should import from `synthetic.datasets`."""

    from app.gamification.modeling.synthetic.datasets import load_fake_expert_review_simulation

    return load_fake_expert_review_simulation()


def load_fake_expert_review_rows() -> list[DatasetRow]:
    """Compatibility export; new code should import from `synthetic.datasets`."""

    from app.gamification.modeling.synthetic.datasets import load_fake_expert_review_rows

    return load_fake_expert_review_rows()


def load_synthetic_expert_review_simulation() -> dict[str, object]:
    """Load the development-only expert-review simulation."""

    from app.gamification.modeling.synthetic.datasets import (
        load_synthetic_expert_review_simulation,
    )

    return load_synthetic_expert_review_simulation()


def load_synthetic_expert_review_rows() -> list[DatasetRow]:
    """Load model-ready rows from the synthetic review simulation."""

    from app.gamification.modeling.synthetic.datasets import load_synthetic_expert_review_rows

    return load_synthetic_expert_review_rows()


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
    "load_fake_expert_review_rows",
    "load_fake_expert_review_simulation",
    "load_synthetic_expert_review_rows",
    "load_synthetic_expert_review_simulation",
    "train_frequency_candidate",
    "train_likelihood_tables",
]
