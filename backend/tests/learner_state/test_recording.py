from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.learner_state.application.recording import (
    LearnerStateRecorder,
    UnknownLearnerError,
    get_learner_state_service,
)
from app.learner_state.application.service import (
    LearnerStateService,
    LearnerStateWindow,
    VisualObservation,
    WindowOrderError,
)
from app.learner_state.application.support_need import LearnerSkillState
from app.learner_state.infrastructure.feature_builder import BehaviorObservation
from tests.learner_state.test_learner_state_service import FakeModels, window
from tests.test_learner_state import create_learner, learner_state_payload


class InMemorySkillStates:
    def __init__(self) -> None:
        self.saved: list[LearnerSkillState] = []

    def save(self, state: LearnerSkillState) -> None:
        self.saved.append(state)

    def get(self, learner_id: UUID, skill_id: str) -> LearnerSkillState | None:
        return next(
            (s for s in reversed(self.saved) if (s.learner_id, s.skill_id) == (learner_id, skill_id)),
            None,
        )


def recorder_with(*, known: set[UUID]) -> tuple[LearnerStateRecorder, InMemorySkillStates]:
    states = InMemorySkillStates()
    recorder = LearnerStateRecorder(
        service=LearnerStateService(models=FakeModels()),
        learner_exists=lambda learner_id: learner_id in known,
        skill_states=states,
    )
    return recorder, states


def test_record_evaluates_and_stores_the_latest_state_per_skill() -> None:
    learner_id = uuid4()
    recorder, states = recorder_with(known={learner_id})

    result = recorder.record(window(1, learner_id=learner_id), skill_id=" MAT-FRC ")

    assert result.window_id == 1
    stored = states.get(learner_id, "MAT-FRC")
    assert stored is not None
    assert stored.session_id == "session-1"
    assert stored.window_id == 1
    assert stored.recommended_action == result.recommended_action


def test_unknown_learner_is_rejected_without_changing_history() -> None:
    learner_id = uuid4()
    known: set[UUID] = set()
    states = InMemorySkillStates()
    recorder = LearnerStateRecorder(
        service=LearnerStateService(models=FakeModels()),
        learner_exists=lambda candidate: candidate in known,
        skill_states=states,
    )

    with pytest.raises(UnknownLearnerError):
        recorder.record(window(1, learner_id=learner_id), skill_id="MAT-FRC")
    assert states.saved == []

    known.add(learner_id)
    assert recorder.record(window(1, learner_id=learner_id), skill_id="MAT-FRC").window_id == 1


@pytest.mark.parametrize("skill_id", ["", "   ", "A" * 17])
def test_invalid_universal_skill_id_is_rejected_before_evaluation(skill_id: str) -> None:
    learner_id = uuid4()
    recorder, states = recorder_with(known={learner_id})

    with pytest.raises(ValidationError):
        recorder.record(window(1, learner_id=learner_id), skill_id=skill_id)
    assert states.saved == []
    assert recorder.record(window(1, learner_id=learner_id), skill_id="MAT-FRC").window_id == 1


def test_window_order_error_is_a_value_error() -> None:
    learner_id = uuid4()
    recorder, _ = recorder_with(known={learner_id})
    recorder.record(window(2, learner_id=learner_id), skill_id="MAT-FRC")

    with pytest.raises(WindowOrderError, match="window_id must increase"):
        recorder.record(window(2, learner_id=learner_id), skill_id="MAT-FRC")
    assert issubclass(WindowOrderError, ValueError)


def test_http_api_and_in_process_callers_share_session_history(client: TestClient) -> None:
    learner_id = create_learner(client)
    response = client.post("/api/v1/learner-state", json=learner_state_payload(learner_id, 1))
    assert response.status_code == 200

    in_process = LearnerStateRecorder(
        service=get_learner_state_service(),
        learner_exists=lambda _: True,
        skill_states=InMemorySkillStates(),
    )
    payload = learner_state_payload(learner_id, 1)
    duplicate = LearnerStateWindow(
        session_id=payload["session_id"],
        learner_id=UUID(learner_id),
        window_id=1,
        timestamp=datetime.now(UTC),
        visual=VisualObservation(**payload["visual"]),
        behavior=BehaviorObservation(**payload["behaviour"]),
    )

    with pytest.raises(WindowOrderError):
        in_process.record(duplicate, skill_id="MAT-FRC")
    assert get_learner_state_service() is get_learner_state_service()
