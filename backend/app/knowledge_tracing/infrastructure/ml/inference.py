"""Inference, equivalent to knowledge_state() in the training script (Cell 11).

The trick: append one extra "query step" to the history, set its skill to the skill being asked
about, its source to paper and its difficulty to the level being asked about, and read the logit
of that last step. All questions run in one batch.
"""

from collections.abc import Sequence

import numpy as np
import torch

from app.knowledge_tracing.infrastructure.ml.model import MindBridgeDKT

PAPER = 0.0


@torch.no_grad()
def predict(
    model: MindBridgeDKT,
    skills: Sequence[int],
    corrects: Sequence[float],
    sources: Sequence[float],
    penalties: Sequence[float],
    query_skills: Sequence[int],
    query_difficulties: Sequence[float],
    query_source: float = PAPER,
) -> np.ndarray:
    """P(correct) for each (query skill, query difficulty) pair, given a history of length >= 1.

    `query_difficulties` are model values (0.0 easy, 0.5 medium, 1.0 hard).
    """
    if len(skills) == 0:
        raise ValueError("history must have at least one attempt")
    n = len(query_skills)

    def with_query(history: Sequence[float] | np.ndarray, extra: np.ndarray) -> torch.Tensor:
        base = torch.tensor(np.asarray(history), dtype=torch.float32)[None].repeat(n, 1)
        return torch.cat([base, torch.as_tensor(extra, dtype=torch.float32)[:, None]], dim=1)

    # one copy of the child's history per skill we want to ask about, each with one extra made-up step at the end
    skill_tensor = torch.cat(
        [
            torch.tensor(list(skills), dtype=torch.long)[None].repeat(n, 1),
            torch.as_tensor(np.asarray(query_skills), dtype=torch.long)[:, None],
        ],
        dim=1,
    )
    corrects_tensor = with_query(corrects, np.zeros(n))  # the answer of the made-up step is not used
    sources_tensor = with_query(sources, np.full(n, float(query_source)))  # ask as if it is a paper question
    penalties_tensor = with_query(penalties, np.zeros(n))
    diffs_tensor = with_query(np.zeros(len(skills)), np.asarray(query_difficulties, dtype=float))

    model.eval()
    logits = model(skill_tensor, corrects_tensor, sources_tensor, penalties_tensor, diffs_tensor)
    # the last logit is the prediction for the made-up question; sigmoid turns it into a chance between 0 and 1
    return torch.sigmoid(logits[:, -1]).numpy()


def skill_probabilities(
    model: MindBridgeDKT,
    skills: Sequence[int],
    corrects: Sequence[float],
    sources: Sequence[float],
    penalties: Sequence[float],
    num_skills: int,
    difficulty: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """(probabilities, attempt counts), one entry per skill, for a paper question of one level."""
    probabilities = predict(
        model,
        skills,
        corrects,
        sources,
        penalties,
        query_skills=np.arange(num_skills),
        query_difficulties=np.full(num_skills, difficulty),
    )
    counts = np.bincount(np.asarray(skills, dtype=int), minlength=num_skills)
    return probabilities, counts


def item_probabilities(
    model: MindBridgeDKT,
    skills: Sequence[int],
    corrects: Sequence[float],
    sources: Sequence[float],
    penalties: Sequence[float],
    num_skills: int,
    difficulties: Sequence[float] = (0.0, 0.5, 1.0),
) -> np.ndarray:
    """P(correct) on a PAPER question for every (skill, difficulty); shape (num_skills, len)."""
    query_skills = np.repeat(np.arange(num_skills), len(difficulties))
    query_difficulties = np.tile(np.asarray(difficulties, dtype=float), num_skills)
    flat = predict(
        model, skills, corrects, sources, penalties, query_skills, query_difficulties
    )
    return flat.reshape(num_skills, len(difficulties))
