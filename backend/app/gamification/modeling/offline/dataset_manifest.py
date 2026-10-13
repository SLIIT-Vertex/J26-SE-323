from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from app.gamification.modeling.offline.dataset_splitting import create_learner_splits
from app.gamification.modeling.shared.artifact_registry import sha256_digest


@dataclass(frozen=True, slots=True)
class DatasetRow:
    episode_id: str
    learner_id: str
    features: Mapping[str, float | int | bool | str | None]
    action_id: str
    reward: float | None
    propensity: float | None
    valid_outcome: bool
    label: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_id: str
    schema_version: str
    source_sha256: str
    exclusion_rules: tuple[str, ...]
    split_seed: int
    learner_splits: Mapping[str, tuple[str, ...]]
    synthetic: bool

    @classmethod
    def build(
        cls,
        rows: Sequence[DatasetRow],
        *,
        dataset_id: str,
        split_seed: int,
        synthetic: bool,
    ) -> "DatasetManifest":
        manifest = cls(
            dataset_id=dataset_id,
            schema_version="offline-dataset-v1",
            source_sha256=sha256_digest([asdict(row) for row in rows]),
            exclusion_rules=("invalid_outcome", "missing_reward"),
            split_seed=split_seed,
            learner_splits=create_learner_splits(
                [row.learner_id for row in rows], split_seed=split_seed
            ),
            synthetic=synthetic,
        )
        manifest.assert_no_learner_leakage()
        return manifest

    def assert_no_learner_leakage(self) -> None:
        groups = [set(values) for values in self.learner_splits.values()]
        if any(left & right for index, left in enumerate(groups) for right in groups[index + 1 :]):
            raise ValueError("a learner cannot occur in multiple dataset splits")

    @property
    def digest(self) -> str:
        return sha256_digest(asdict(self))
