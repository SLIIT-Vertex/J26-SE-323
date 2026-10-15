import hashlib
import math
from collections.abc import Sequence


def create_learner_splits(
    learners: Sequence[str], *, split_seed: int
) -> dict[str, tuple[str, ...]]:
    """Create deterministic learner-disjoint train, validation, and test assignments."""

    ranked = sorted(
        set(learners),
        key=lambda learner: hashlib.sha256(f"{split_seed}:{learner}".encode()).hexdigest(),
    )
    train_end = math.ceil(len(ranked) * 0.6)
    validation_end = train_end + math.floor(len(ranked) * 0.2)
    return {
        "train": tuple(ranked[:train_end]),
        "validation": tuple(ranked[train_end:validation_end]),
        "test": tuple(ranked[validation_end:]),
    }
