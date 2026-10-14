from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.learner_state.application.service import (
    LearnerStateService,
    LearnerStateWindow,
    VisualObservation,
    _choose_recommended_action,
)
from app.learner_state.infrastructure.feature_builder import BehaviorObservation


class FakeModels:
    """Returns fixed probabilities and records the features it receives."""

    def __init__(
        self,
        *,
        confusion_visual: float = 0.1,
        confusion_behavior: float = 0.1,
        disengagement_visual: float = 0.1,
        disengagement_behavior: float = 0.1,
    ) -> None:
        self.confusion_visual = confusion_visual
        self.confusion_behavior = confusion_behavior
        self.disengagement_visual = disengagement_visual
        self.disengagement_behavior = disengagement_behavior
        self.disengagement_behavior_features: list[dict[str, float | None]] = []

    def predict_confusion_visual(self, features: dict[str, float | None]) -> float:
        return self.confusion_visual

    def predict_confusion_behavior(self, features: dict[str, float | None]) -> float:
        return self.confusion_behavior

    def predict_disengagement_visual(self, features: dict[str, float | None]) -> float:
        return self.disengagement_visual

    def predict_disengagement_behavior(self, features: dict[str, float | None]) -> float:
        self.disengagement_behavior_features.append(features)
        return self.disengagement_behavior


def window(
    window_id: int,
    *,
    learner_id: UUID,
    session_id: str = "session-1",
    task_progress: float | None = None,
) -> LearnerStateWindow:
    return LearnerStateWindow(
        session_id=session_id,
        learner_id=learner_id,
        window_id=window_id,
        timestamp=datetime(2026, 10, 13, tzinfo=UTC),
        visual=VisualObservation(
            mean_eye_openness=0.3,
            std_eye_openness=0.05,
            mean_gaze_ratio=0.5,
            std_gaze_ratio=0.05,
            mean_pitch=0.0,
            mean_yaw=0.0,
            mean_roll=0.0,
            mean_abs_pitch=0.0,
            mean_abs_yaw=0.0,
            mean_abs_roll=0.0,
            face_visibility_ratio=1.0,
        ),
        behavior=BehaviorObservation(
            correct=0.0,
            bottom_hint=0.0,
            hint_count=1.0,
            attempt_count=2.0,
            ms_first_response=10000.0,
            overlap_time=20000.0,
            first_action=0.0,
            position=1.0,
            original=1.0,
        ),
        task_progress=task_progress,
    )


def service_with(**probabilities: float) -> tuple[LearnerStateService, FakeModels]:
    models = FakeModels(**probabilities)
    return LearnerStateService(models=models), models


def test_low_evidence_recommends_no_action() -> None:
    service, _ = service_with()

    result = service.evaluate(window(1, learner_id=uuid4()))

    assert result.confusion.state == "no_confusion"
    assert result.disengagement.state == "engaged"
    assert result.recommended_action == "none"
    assert result.confusion.persistent_count == 0


def test_persistent_disengagement_requests_reengagement() -> None:
    service, _ = service_with(disengagement_visual=0.95, disengagement_behavior=0.95)
    learner_id = uuid4()

    first = service.evaluate(window(1, learner_id=learner_id))
    second = service.evaluate(window(2, learner_id=learner_id))

    assert first.disengagement.state == "transient_disengagement"
    assert first.recommended_action == "monitor"
    assert second.disengagement.state == "persistent_disengagement"
    assert second.disengagement.persistent_count == 2
    assert second.disengagement.temporal_score >= 0.60
    assert second.recommended_action == "request_reengagement_support"


def test_reengagement_has_priority_over_tutor_support() -> None:
    service, _ = service_with(
        confusion_visual=0.95,
        confusion_behavior=0.95,
        disengagement_visual=0.95,
        disengagement_behavior=0.95,
    )
    learner_id = uuid4()

    service.evaluate(window(1, learner_id=learner_id))
    result = service.evaluate(window(2, learner_id=learner_id))

    assert result.confusion.support_need == "request_tutor_support"
    assert result.disengagement.support_need == "request_reengagement_support"
    assert result.recommended_action == "request_reengagement_support"


def test_rising_task_progress_makes_persistent_confusion_productive() -> None:
    service, _ = service_with(confusion_visual=0.95, confusion_behavior=0.95)
    learner_id = uuid4()

    service.evaluate(window(1, learner_id=learner_id, task_progress=0.20))
    result = service.evaluate(window(2, learner_id=learner_id, task_progress=0.30))

    assert result.confusion.state == "productive_confusion"
    assert result.recommended_action == "monitor"


def test_stalled_task_progress_makes_persistent_confusion_intervention_worthy() -> None:
    service, _ = service_with(confusion_visual=0.95, confusion_behavior=0.95)
    learner_id = uuid4()

    service.evaluate(window(1, learner_id=learner_id, task_progress=0.60))
    result = service.evaluate(window(2, learner_id=learner_id, task_progress=0.60))

    assert result.confusion.state == "intervention_worthy_confusion"
    assert result.recommended_action == "request_tutor_support"


def test_confusion_reliability_does_not_depend_on_session_length() -> None:
    service, _ = service_with(confusion_visual=0.78, confusion_behavior=0.60)
    learner_id = uuid4()

    results = [service.evaluate(window(w, learner_id=learner_id)) for w in range(1, 26)]

    confusion_reliability = {r.confusion.behavior_reliability for r in results}
    disengagement_reliability = [r.disengagement.behavior_reliability for r in results]
    assert confusion_reliability == {1.0}
    assert disengagement_reliability[0] == pytest.approx(0.70)
    assert disengagement_reliability[-1] == pytest.approx(1.0)
    assert {r.confusion.state for r in results[2:]} == {results[2].confusion.state}


@pytest.mark.parametrize("window_id", [1, 0])
def test_duplicate_or_older_window_is_rejected(window_id: int) -> None:
    service, _ = service_with()
    learner_id = uuid4()
    service.evaluate(window(1, learner_id=learner_id))

    with pytest.raises(ValueError, match="window_id must increase"):
        service.evaluate(window(window_id, learner_id=learner_id))


def test_rejected_window_does_not_change_history() -> None:
    service, models = service_with()
    learner_id = uuid4()

    service.evaluate(window(1, learner_id=learner_id))
    with pytest.raises(ValueError):
        service.evaluate(window(1, learner_id=learner_id))
    service.evaluate(window(5, learner_id=learner_id))

    assert len(models.disengagement_behavior_features) == 2
    assert models.disengagement_behavior_features[-1]["history_confidence"] == pytest.approx(
        1 / 20
    )


def test_sessions_are_isolated_by_session_and_learner() -> None:
    service, _ = service_with()
    learner_id = uuid4()

    service.evaluate(window(1, learner_id=learner_id))
    service.evaluate(window(1, learner_id=uuid4()))
    service.evaluate(window(1, learner_id=learner_id, session_id="session-2"))


def test_clear_session_resets_history() -> None:
    service, _ = service_with()
    learner_id = uuid4()
    service.evaluate(window(1, learner_id=learner_id))

    service.clear_session(session_id="session-1", learner_id=learner_id)

    service.evaluate(window(1, learner_id=learner_id))


@pytest.mark.parametrize(
    ("confusion_support", "disengagement_support", "expected"),
    [
        ("request_tutor_support", "request_reengagement_support", "request_reengagement_support"),
        ("request_tutor_support", "collect_more_evidence", "request_tutor_support"),
        ("collect_more_evidence", "monitor", "collect_more_evidence"),
        ("monitor", "collect_more_evidence", "collect_more_evidence"),
        ("monitor", "none", "monitor"),
        ("none", "monitor", "monitor"),
        ("none", "none", "none"),
    ],
)
def test_recommended_action_priority(
    confusion_support: str,
    disengagement_support: str,
    expected: str,
) -> None:
    assert (
        _choose_recommended_action(
            confusion_support=confusion_support,
            disengagement_support=disengagement_support,
        )
        == expected
    )
