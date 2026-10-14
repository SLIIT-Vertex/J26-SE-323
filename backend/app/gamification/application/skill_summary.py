"""Derived learner-skill report. Supported and unsupported attempts stay separate."""

from datetime import datetime
from uuid import UUID

from app.gamification.application.ports import SkillSummaryStore
from app.gamification.application.records import LearnerSkillSummary

SUMMARY_VERSION = "learner-skill-summary-v1"


class UpdateLearnerSkillSummary:
    def __init__(self, store: SkillSummaryStore) -> None:
        self._store = store

    def record_attempt(
        self,
        *,
        learner_id: UUID,
        skill_id: str,
        correct: bool,
        supported: bool,
        at: datetime,
    ) -> LearnerSkillSummary:
        current = self._store.get(learner_id=learner_id, skill_id=skill_id)
        unsupported = 0 if current is None else current.unsupported_attempts
        supported_attempts = 0 if current is None else current.supported_attempts
        independent_correct = _correct_count(
            None if current is None else current.independent_accuracy, unsupported
        )
        supported_correct = _correct_count(
            None if current is None else current.supported_accuracy, supported_attempts
        )
        if supported:
            supported_attempts += 1
            supported_correct += int(correct)
        else:
            unsupported += 1
            independent_correct += int(correct)
        summary = _rebuild(
            current,
            learner_id=learner_id,
            skill_id=skill_id,
            unsupported_attempts=unsupported,
            supported_attempts=supported_attempts,
            independent_accuracy=_ratio(independent_correct, unsupported),
            supported_accuracy=_ratio(supported_correct, supported_attempts),
            at=at,
        )
        self._store.save(summary)
        return summary

    def record_valid_gain(
        self,
        *,
        learner_id: UUID,
        skill_id: str,
        raw_gain: float,
        at: datetime,
    ) -> LearnerSkillSummary:
        current = self._store.get(learner_id=learner_id, skill_id=skill_id)
        count = 0 if current is None else current.valid_outcome_count
        total = (
            0.0
            if current is None or current.mean_independence_gain is None
            else (current.mean_independence_gain * count)
        )
        count += 1
        total += raw_gain
        summary = _rebuild(
            current,
            learner_id=learner_id,
            skill_id=skill_id,
            unsupported_attempts=0 if current is None else current.unsupported_attempts,
            supported_attempts=0 if current is None else current.supported_attempts,
            independent_accuracy=None if current is None else current.independent_accuracy,
            supported_accuracy=None if current is None else current.supported_accuracy,
            at=at,
            valid_outcome_count=count,
            mean_independence_gain=total / count,
        )
        self._store.save(summary)
        return summary


def _rebuild(
    current: LearnerSkillSummary | None,
    *,
    learner_id: UUID,
    skill_id: str,
    unsupported_attempts: int,
    supported_attempts: int,
    independent_accuracy: float | None,
    supported_accuracy: float | None,
    at: datetime,
    valid_outcome_count: int | None = None,
    mean_independence_gain: float | None = None,
) -> LearnerSkillSummary:
    total = unsupported_attempts + supported_attempts
    if valid_outcome_count is None:
        valid_outcome_count = 0 if current is None else current.valid_outcome_count
    if mean_independence_gain is None and current is not None:
        mean_independence_gain = current.mean_independence_gain
    return LearnerSkillSummary(
        learner_id=learner_id,
        skill_id=skill_id,
        unsupported_attempts=unsupported_attempts,
        supported_attempts=supported_attempts,
        independent_accuracy=independent_accuracy,
        supported_accuracy=supported_accuracy,
        mean_independence_gain=mean_independence_gain,
        support_dependency_index=(supported_attempts / total) if total else None,
        valid_outcome_count=valid_outcome_count,
        last_practiced_at=at,
        summary_version=SUMMARY_VERSION,
        updated_at=at,
    )


def _correct_count(accuracy: float | None, attempts: int) -> int:
    if accuracy is None or attempts == 0:
        return 0
    return int(round(accuracy * attempts))


def _ratio(correct: int, attempts: int) -> float | None:
    if attempts == 0:
        return None
    return correct / attempts
