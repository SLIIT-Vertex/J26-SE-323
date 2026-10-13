from typing import Mapping, Protocol, Sequence

from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle


class LabelledRow(Protocol):
    learner_id: str
    label: str | None


class TrainingManifest(Protocol):
    learner_splits: Mapping[str, tuple[str, ...]]

    @property
    def digest(self) -> str: ...

    @property
    def synthetic(self) -> bool: ...

    def assert_no_learner_leakage(self) -> None: ...


def train_frequency_candidate(
    rows: Sequence[LabelledRow],
    *,
    manifest: TrainingManifest,
    model_name: str,
    model_version: str,
    source_commit: str,
    feature_definition_version: str,
    seed: int,
) -> ModelArtifactBundle:
    """Create a reproducible baseline from only the manifest's training learners."""

    manifest.assert_no_learner_leakage()
    train_learners = set(manifest.learner_splits["train"])
    labels = [row.label for row in rows if row.learner_id in train_learners and row.label]
    if not labels:
        raise ValueError("training split contains no supplied labels")
    counts = {label: labels.count(label) for label in sorted(set(labels))}
    total = len(labels)
    return ModelArtifactBundle.create(
        model_name=model_name,
        model_version=model_version,
        source_commit=source_commit,
        feature_definition_version=feature_definition_version,
        manifest=manifest,
        seed=seed,
        parameters={"class_priors": {label: count / total for label, count in counts.items()}},
    )
