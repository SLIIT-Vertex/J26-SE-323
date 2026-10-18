import inspect
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.gamification.application.session_play import LearnerStateAnswerGateway
from app.learner_state.application.recording import (
    UnknownLearnerError,
    get_learner_state_service,
)
from app.learner_state.application.service import (
    LearnerStateEvaluation,
    LearnerStateService,
    LearnerStateWindow,
    WindowOrderError,
)
from app.learner_state.infrastructure import game_answers
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.learner_state.infrastructure.game_answers import (
    NO_VISUAL_EVIDENCE,
    GameAnswerRecorder,
    behaviour_from_game_answer,
    visual_from_game_answer,
)
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from tests.learner_state.test_learner_state_service import FakeModels

OBSERVED_AT = datetime(2026, 10, 18, 9, 30, tzinfo=UTC)
VISUAL = {
    "mean_eye_openness": 0.3,
    "std_eye_openness": 0.05,
    "mean_gaze_ratio": 0.5,
    "std_gaze_ratio": 0.05,
    "mean_pitch": 2.0,
    "mean_yaw": -3.0,
    "mean_roll": 1.0,
    "mean_abs_pitch": 4.0,
    "mean_abs_yaw": 5.0,
    "mean_abs_roll": 2.0,
    "face_visibility_ratio": 0.9,
}


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def add_learner(session_factory: sessionmaker[Session]) -> UUID:
    with session_factory() as session:
        learner = SqlAlchemyLearnerRepository(session).add(
            Learner(id=uuid4(), grade=5, preferred_language="si")
        )
    return learner.id


def answer(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "session_id": uuid4(),
        "learner_id": uuid4(),
        "window_id": 1,
        "skill_id": "MAT-FRC",
        "observed_at": OBSERVED_AT,
        "correct": False,
        "response_time_ms": 12_000,
        "supported": False,
        "hint_count": 0,
        "visual": VISUAL,
    }
    values.update(overrides)
    return values


def test_record_answer_matches_the_game_gateway_protocol() -> None:
    expected = inspect.signature(LearnerStateAnswerGateway.record_answer).parameters
    actual = inspect.signature(GameAnswerRecorder.record_answer).parameters

    assert list(actual) == list(expected)
    assert [p.kind for p in actual.values()] == [p.kind for p in expected.values()]


def test_game_answer_maps_to_behaviour_fields_without_invented_values() -> None:
    behaviour = behaviour_from_game_answer(correct=True, response_time_ms=8_500, hint_count=0)

    assert behaviour.correct == 1.0
    assert behaviour.bottom_hint is None
    assert behaviour.hint_count == 0.0
    assert behaviour.attempt_count == 1.0
    assert behaviour.ms_first_response == 8_500.0
    assert behaviour.overlap_time == 8_500.0
    assert behaviour.original == 1.0
    assert behaviour_from_game_answer(correct=False, response_time_ms=1, hint_count=1).correct == 0.0


def test_visual_snapshot_is_copied_and_missing_camera_gives_no_visual_evidence() -> None:
    assert visual_from_game_answer(VISUAL).face_visibility_ratio == 0.9
    assert visual_from_game_answer(VISUAL).mean_yaw == -3.0
    assert visual_from_game_answer(None) == NO_VISUAL_EVIDENCE
    assert NO_VISUAL_EVIDENCE.face_visibility_ratio == 0.0

    incomplete = {k: v for k, v in VISUAL.items() if k != "mean_roll"}
    with pytest.raises(KeyError):
        visual_from_game_answer(incomplete)


def test_records_the_window_and_returns_its_recommended_action(
    session_factory: sessionmaker[Session],
) -> None:
    learner_id = add_learner(session_factory)
    session_id = uuid4()
    recorder = GameAnswerRecorder(session_factory=session_factory, service=LearnerStateService())

    action = recorder.record_answer(
        **answer(session_id=session_id, learner_id=learner_id, skill_id=" MAT-FRC ")
    )

    assert action in {
        "none",
        "monitor",
        "request_tutor_support",
        "request_reengagement_support",
        "collect_more_evidence",
    }
    with session_factory() as session:
        stored = SqlAlchemyLearnerSkillStateRepository(session).get(learner_id, "MAT-FRC")
    assert stored is not None
    assert stored.session_id == str(session_id)
    assert stored.window_id == 1
    assert stored.recommended_action == action


class RecordingService(LearnerStateService):
    def __init__(self) -> None:
        super().__init__(models=FakeModels())
        self.evaluations: list[LearnerStateEvaluation] = []

    def evaluate(self, window: LearnerStateWindow) -> LearnerStateEvaluation:
        evaluation = super().evaluate(window)
        self.evaluations.append(evaluation)
        return evaluation


def test_without_a_camera_fusion_follows_the_behavioural_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    learner_id = add_learner(session_factory)
    service = RecordingService()
    recorder = GameAnswerRecorder(session_factory=session_factory, service=service)

    recorder.record_answer(**answer(learner_id=learner_id, visual=None))

    for signal in (service.evaluations[0].confusion, service.evaluations[0].disengagement):
        assert signal.visual_reliability == 0.0
        assert signal.behavior_reliability > 0.0
        # Visual weight 0 and no conflict: confidence is the behavioural reliability.
        assert signal.confidence == pytest.approx(signal.behavior_reliability)


def test_unknown_response_time_records_nothing(session_factory: sessionmaker[Session]) -> None:
    learner_id = add_learner(session_factory)
    session_id = uuid4()
    recorder = GameAnswerRecorder(
        session_factory=session_factory, service=LearnerStateService(models=FakeModels())
    )

    assert recorder.record_answer(
        **answer(session_id=session_id, learner_id=learner_id, response_time_ms=None)
    ) is None
    with session_factory() as session:
        assert SqlAlchemyLearnerSkillStateRepository(session).get(learner_id, "MAT-FRC") is None

    # The skipped window leaves a gap, which the next window may use.
    assert recorder.record_answer(
        **answer(session_id=session_id, learner_id=learner_id, window_id=2)
    ) is not None


def test_errors_are_logged_and_raised_to_the_game(
    session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tests that run Alembic's fileConfig disable every logger that already exists.
    monkeypatch.setattr(game_answers.logger, "disabled", False)
    recorder = GameAnswerRecorder(
        session_factory=session_factory, service=LearnerStateService(models=FakeModels())
    )

    with caplog.at_level(logging.WARNING), pytest.raises(UnknownLearnerError):
        recorder.record_answer(**answer())
    assert "was not recorded" in caplog.text

    learner_id = add_learner(session_factory)
    session_id = uuid4()
    recorder.record_answer(**answer(session_id=session_id, learner_id=learner_id, window_id=3))
    with pytest.raises(WindowOrderError):
        recorder.record_answer(**answer(session_id=session_id, learner_id=learner_id, window_id=3))


def test_uses_the_shared_service_by_default(session_factory: sessionmaker[Session]) -> None:
    recorder = GameAnswerRecorder(session_factory=session_factory)

    assert recorder._service is get_learner_state_service()
