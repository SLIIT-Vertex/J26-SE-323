"""Gathers one learner's inputs and asks `paper_selection` for the weekly paper.

Questions attempted in the last 30 days are never offered again. (Questions already printed on
the learner's last papers will be excluded too, once papers are stored.)
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import numpy as np

from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_selection import (
    DEFAULT_CONFIG,
    Candidate,
    PaperParams,
    Selection,
    SelectionConfig,
    SkillState,
    layout_height_mm,
    select_questions,
)
from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import FeatureSpec
from app.knowledge_tracing.domain.mastery import MasterySnapshot

RECENT_DAYS = 30
LANGUAGES = ("si", "ta")
DEFAULT_LANGUAGE = "si"


@dataclass(frozen=True, slots=True)
class QuestionRow:
    question_id: str
    skill_code: str
    difficulty: str
    est_seconds: int
    width_px: int
    height_px: int


@dataclass(frozen=True, slots=True)
class SkillActivity:
    digital_attempts: int = 0
    digital_correct: int = 0
    paper_attempts: int = 0


class PaperInputRepository(Protocol):
    def learner_language(self, learner_id: UUID) -> str | None: ...

    def skill_catalog(self) -> list[tuple[str, str, int]]:
        """(code, area, sort_index) for every skill."""
        ...

    def skill_activity(self, learner_id: UUID) -> dict[str, SkillActivity]: ...

    def recently_answered(self, learner_id: UUID, since: datetime) -> set[str]: ...

    def question_rows(self, language: str) -> list[QuestionRow]: ...

    def previous_snapshot(self, learner_id: UUID) -> MasterySnapshot | None:
        """The snapshot before the latest one."""
        ...

    def history(self, learner_id: UUID, limit: int | None) -> list[HistoryItem]: ...


class ItemProbabilityEstimator(Protocol):
    def item_probabilities(self, history: list[HistoryItem]) -> np.ndarray | None: ...


class PaperPlanner:
    def __init__(
        self,
        inputs: PaperInputRepository,
        mastery: MasteryService,
        estimator: ItemProbabilityEstimator,
        spec: FeatureSpec,
        config: SelectionConfig = DEFAULT_CONFIG,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.inputs = inputs
        self.mastery = mastery
        self.estimator = estimator
        self.spec = spec
        self.config = config
        self.now = now

    def plan(
        self,
        learner_id: UUID,
        params: PaperParams = PaperParams(),  # noqa: B008
        language: str | None = None,
    ) -> Selection:
        """The questions of this week's paper for one learner (not yet laid out or printed)."""
        snapshot = self.mastery.current(learner_id)  # raises LearnerNotFoundError
        language = self._language(learner_id, language)

        previous = self.inputs.previous_snapshot(learner_id)
        was_weak = {
            s.code
            for s in (previous.skills if previous else ())
            if s.mastery is not None and s.mastery < self.config.weak_enter
        }
        activity = self.inputs.skill_activity(learner_id)
        catalog = {code: (area, index) for code, area, index in self.inputs.skill_catalog()}
        by_snapshot = {s.code: s for s in snapshot.skills}

        states: list[SkillState] = []
        for code in self.spec.skills:
            area, index = catalog[code]
            seen = activity.get(code, SkillActivity())
            states.append(
                SkillState(
                    code=code,
                    area=area,
                    sort_index=index,
                    mastery=by_snapshot[code].mastery,
                    digital_attempts=seen.digital_attempts,
                    digital_correct=seen.digital_correct,
                    paper_attempts=seen.paper_attempts,
                    was_weak=code in was_weak,
                )
            )

        history = self.inputs.history(learner_id, self.spec.history_cap)
        item_probs = self.estimator.item_probabilities(history)

        since = self.now() - timedelta(days=RECENT_DAYS)
        recent = self.inputs.recently_answered(learner_id, since)
        candidates = [
            Candidate(
                question_id=row.question_id,
                skill_code=row.skill_code,
                difficulty=row.difficulty,
                est_seconds=row.est_seconds,
                height_mm=layout_height_mm(row.width_px, row.height_px, self.config),
            )
            for row in self.inputs.question_rows(language)
            if row.question_id not in recent
        ]
        return select_questions(states, item_probs, candidates, params, self.config)

    def _language(self, learner_id: UUID, requested: str | None) -> str:
        if requested in LANGUAGES:
            return str(requested)
        preferred = self.inputs.learner_language(learner_id)
        return preferred if preferred in LANGUAGES else DEFAULT_LANGUAGE
