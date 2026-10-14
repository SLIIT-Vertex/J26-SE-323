"""The loaded knowledge model: history in, mastery per skill out. CPU only."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import (
    FeatureSpec,
    get_feature_spec,
    resolve_path,
)
from app.knowledge_tracing.infrastructure.ml.features import build_arrays
from app.knowledge_tracing.infrastructure.ml.inference import (
    item_probabilities,
    skill_probabilities,
)
from app.knowledge_tracing.infrastructure.ml.model import MindBridgeDKT

MODEL_FAMILY = "dkt-v2.1"
DIFFICULTY_ORDER = ("easy", "medium", "hard")
MASTERY_DECIMALS = 3  # the same rounding as the training script


@dataclass(frozen=True, slots=True)
class SkillMastery:
    """Chance of answering a MEDIUM-difficulty PAPER question of this skill correctly.

    `mastery` is None when the history holds fewer than the minimum attempts for the skill.
    `attempts` counts the answers inside the history window given to the model.
    """

    code: str
    index: int
    mastery: float | None
    attempts: int


class KnowledgeModel:
    def __init__(self, model: MindBridgeDKT, spec: FeatureSpec, version: str) -> None:
        self.model = model.eval()
        self.spec = spec
        self.version = version

    @classmethod
    def load(cls, weights_path: str | Path, spec: FeatureSpec) -> "KnowledgeModel":
        path = resolve_path(str(weights_path))
        torch.set_num_threads(1)  # avoid thread fights with the web server
        model = MindBridgeDKT(num_skills=len(spec.skills), use_source=True)
        state = torch.load(path, map_location="cpu", weights_only=True)
        model.load_state_dict(state)  # strict: a different architecture fails loudly
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        return cls(model, spec, f"{MODEL_FAMILY}-{digest}")

    def mastery(self, history: Sequence[HistoryItem]) -> list[SkillMastery]:
        """One entry per skill in spec order. An empty history gives all-unknown."""
        arrays = build_arrays(history, self.spec.history_cap)
        if len(arrays) == 0:
            return [SkillMastery(code, i, None, 0) for i, code in enumerate(self.spec.skills)]
        probabilities, counts = skill_probabilities(
            self.model,
            arrays.skills,
            arrays.corrects,
            arrays.sources,
            arrays.penalties,
            num_skills=len(self.spec.skills),
            difficulty=self.spec.difficulty_values["medium"],
        )
        minimum = self.spec.min_attempts_for_known_skill
        return [
            SkillMastery(
                code=code,
                index=index,
                mastery=(
                    round(float(probabilities[index]), MASTERY_DECIMALS)
                    if counts[index] >= minimum
                    else None
                ),
                attempts=int(counts[index]),
            )
            for index, code in enumerate(self.spec.skills)
        ]

    def item_probabilities(self, history: Sequence[HistoryItem]) -> np.ndarray | None:
        """P(correct) on a paper question per (skill, easy/medium/hard); shape (30, 3).

        None for a brand-new learner: the paper generator then uses diagnostic mode.
        Computed for unknown skills too; the generator decides how to treat those.
        """
        arrays = build_arrays(history, self.spec.history_cap)
        if len(arrays) == 0:
            return None
        return item_probabilities(
            self.model,
            arrays.skills,
            arrays.corrects,
            arrays.sources,
            arrays.penalties,
            num_skills=len(self.spec.skills),
            difficulties=[self.spec.difficulty_values[name] for name in DIFFICULTY_ORDER],
        )


@lru_cache
def get_knowledge_model() -> KnowledgeModel:
    from app.config import get_settings

    return KnowledgeModel.load(get_settings().model_weights_path, get_feature_spec())
