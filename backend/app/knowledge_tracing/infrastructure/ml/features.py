"""Turns a learner's stored history into the arrays the model reads."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.knowledge_tracing.domain.attempt import HistoryItem


@dataclass(frozen=True, slots=True)
class HistoryArrays:
    skills: list[int]
    corrects: list[float]
    sources: list[float]
    penalties: list[float]

    def __len__(self) -> int:
        return len(self.skills)


def build_arrays(history: Sequence[HistoryItem], cap: int) -> HistoryArrays:
    """The last `cap` attempts, in the order given (the loader returns them oldest first).

    Only skill, correctness, source and penalty are fed to the model for past steps;
    difficulty is used for the question being asked, not for history.
    """
    # only the latest 140 answers: the model was trained on histories of at most 140 steps
    window = list(history)[-cap:] if cap > 0 else []
    return HistoryArrays(
        skills=[item.skill_index for item in window],
        corrects=[1.0 if item.correct else 0.0 for item in window],
        sources=[float(item.source) for item in window],
        penalties=[float(item.penalty) for item in window],
    )
