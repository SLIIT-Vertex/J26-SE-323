"""Learner-state evidence recorded after scored adventure answers (silent mode)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION
from app.gamification.api.learning_flow_router import AnswerRequest
from app.gamification.application.classroom_action_quest_flow import ClassroomActionQuestFlow
from app.gamification.application.learner_state_answers import (
    LEARNER_STATE_CAMERA_PURPOSE,
    camera_consent_granted,
    record_scored_answer,
)
from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.application.records import ConsentDecision
from app.gamification.content.fraction_adventure import ATOMIC_SKILLS
from app.gamification.domain.types import ContractVersion
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.gamification.infrastructure.memory import InMemoryConsentStore
from app.learner_state.infrastructure.db.repository import SqlAlchemyLearnerSkillStateRepository
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel
from tests.gamification.content.test_fraction_adventure import response_for
from tests.test_learner_state import create_learner

LEARNER = UUID("00000000-0000-4000-8000-000000000909")
# Consent decided before any test run, so the flows' real clock is always later.
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
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


class RecordingGateway:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail = fail

    def record_answer(self, **values: object) -> str | None:
        if self.fail:
            raise RuntimeError("learner-state unavailable")
        self.calls.append(values)
        return "monitor"


def consent(*, granted: bool = True, decided_at: datetime = NOW, expires_at=None):
    return InMemoryConsentStore(
        [
            ConsentDecision(
                learner_id=LEARNER,
                purpose=LEARNER_STATE_CAMERA_PURPOSE,
                granted=granted,
                consent_version="learner-state-camera-v1",
                decided_at=decided_at,
                expires_at=expires_at,
                contract_version=ContractVersion("consent-decision-v1"),
            )
        ]
    )


def record(gateway, consent_store, **overrides):
    values = {
        "session_id": uuid4(),
        "learner_id": LEARNER,
        "skill_id": "MAT-FRC",
        "at": NOW + timedelta(minutes=1),
        "correct": False,
        "response_time_ms": 7000,
        "visual": VISUAL,
    } | overrides
    return record_scored_answer(gateway, consent_store, **values)


def test_camera_values_are_passed_only_with_current_consent() -> None:
    later = NOW + timedelta(minutes=1)
    assert camera_consent_granted(consent(), learner_id=LEARNER, at=later)
    assert not camera_consent_granted(None, learner_id=LEARNER, at=later)
    assert not camera_consent_granted(InMemoryConsentStore([]), learner_id=LEARNER, at=later)
    assert not camera_consent_granted(consent(granted=False), learner_id=LEARNER, at=later)
    assert not camera_consent_granted(consent(decided_at=later + timedelta(1)), learner_id=LEARNER, at=later)
    assert not camera_consent_granted(consent(expires_at=later), learner_id=LEARNER, at=later)


def test_behaviour_is_recorded_without_consent_but_camera_values_are_not() -> None:
    gateway = RecordingGateway()

    assert record(gateway, consent()) == "monitor"
    assert record(gateway, consent(granted=False)) == "monitor"

    assert gateway.calls[0]["visual"] == VISUAL
    assert gateway.calls[1]["visual"] is None
    call = gateway.calls[0]
    assert call["window_id"] == int((NOW + timedelta(minutes=1)).timestamp() * 1000)
    assert (call["supported"], call["hint_count"], call["skill_id"]) == (False, 0, "MAT-FRC")


def test_a_failing_or_missing_gateway_never_fails_the_answer() -> None:
    assert record(RecordingGateway(fail=True), consent()) is None
    assert record(None, consent()) is None


@pytest.fixture
def adventure():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=NOW, updated_at=NOW))
    session.commit()
    gateway = RecordingGateway()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=RecordingEvidencePublisher(),
        learner_state=gateway,
        camera_consent=consent(),
    )
    yield flow, gateway
    session.close()


def open_fraction_episode(flow: LearningFlowOrchestrator) -> tuple[UUID, dict[str, object]]:
    skill = ATOMIC_SKILLS[0].skill_id
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-05",
        atomic_skill_id=skill,
        idempotency_key=f"open:{uuid4()}",
    )
    episode = UUID(opened["episode_id"])
    item = flow.reconstruct(episode)["state"]["presentations"][0]
    correct = response_for(type("Item", (), {"game_data": item["game_data"]})())
    return episode, correct | {
        "presentation_id": item["presentation_id"],
        "item_revision_id": item["revision_id"],
        "interaction_version": "constructed-response-v1",
    }


def test_each_scored_adventure_answer_is_recorded_once(adventure) -> None:
    flow, gateway = adventure
    episode, answer = open_fraction_episode(flow)
    app_session = uuid4()

    def submit():
        return flow.submit_before(
            episode,
            option_id=None,
            constructed_response=answer,
            response_time_ms=6500,
            idempotency_key="before:once",
            visual=VISUAL,
            learner_state_session_id=app_session,
        )

    first = submit()
    replay = submit()

    assert replay == first
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["session_id"] == app_session
    assert call["learner_id"] == LEARNER
    assert call["skill_id"] == "MAT-FRC"
    assert call["correct"] is True
    assert call["response_time_ms"] == 6500
    assert call["visual"] == VISUAL


def test_the_episode_session_is_used_without_an_app_session(adventure) -> None:
    flow, gateway = adventure
    episode, answer = open_fraction_episode(flow)

    flow.submit_before(
        episode,
        option_id=None,
        constructed_response=answer,
        response_time_ms=None,
        idempotency_key="before:no-app-session",
    )

    state = flow.reconstruct(episode)["state"]
    assert gateway.calls[0]["session_id"] == UUID(state["session_id"])
    assert gateway.calls[0]["visual"] is None
    assert gateway.calls[0]["response_time_ms"] is None


def test_english_answers_are_not_recorded() -> None:
    gateway = RecordingGateway()
    flow = ClassroomActionQuestFlow(None, None, None, learner_state=gateway)  # type: ignore[arg-type]

    flow._record_learner_state(
        {
            "state": {"session_id": str(uuid4()), "learner_id": str(LEARNER)},
            "score": {"correct": True, "response_time_ms": 1000},
            "at": NOW,
        },
        VISUAL,
        None,
    )

    assert ClassroomActionQuestFlow.records_learner_state is False
    assert gateway.calls == []


API = "/api/v1/development/learning-flow"


def headers(learner: str, *, role: str = "learner", key: str | None = None) -> dict[str, str]:
    values = {"X-Dev-Principal": NOT_FOR_PRODUCTION, "X-Dev-Role": role}
    if role == "learner":
        values["X-Learner-Id"] = learner
    if key is not None:
        values["Idempotency-Key"] = key
    return values


def test_camera_consent_can_be_given_read_and_withdrawn(client: TestClient) -> None:
    learner = create_learner(client)
    path = f"{API}/consents/learner-state-camera"

    assert client.get(path, headers=headers(learner)).json() == {"granted": False, "decided_at": None}
    assert client.put(path, json={"granted": True}, headers=headers(learner)).json()["granted"]
    assert client.get(path, headers=headers(learner)).json()["granted"] is True
    assert client.put(path, json={"granted": False}, headers=headers(learner)).json()["granted"] is False
    assert client.put(path, json={"granted": True}, headers=headers(str(uuid4()))).status_code == 404


def test_an_adventure_answer_reaches_learner_state_end_to_end(client: TestClient) -> None:
    learner = create_learner(client)
    client.put(
        f"{API}/consents/learner-state-camera", json={"granted": True}, headers=headers(learner)
    )
    opened = client.post(
        f"{API}/episodes",
        json={
            "learner_id": learner,
            "session_id": str(uuid4()),
            "grade": 5,
            "medium": "si",
            "condition": "proposed",
            "environment": "development",
            "allow_draft": True,
            "area_id": "G5-AREA-MAT-05",
            "atomic_skill_id": ATOMIC_SKILLS[0].skill_id,
        },
        headers=headers(learner, key="open"),
    )
    assert opened.status_code == 200, opened.text
    episode = opened.json()["episode_id"]
    state = client.get(
        f"{API}/episodes/{episode}/reconstruction", headers=headers(learner, role="researcher")
    ).json()["state"]
    item = state["presentations"][0]
    answer = response_for(type("Item", (), {"game_data": item["game_data"]})()) | {
        "presentation_id": item["presentation_id"],
        "item_revision_id": item["revision_id"],
        "interaction_version": "constructed-response-v1",
    }
    app_session = str(uuid4())

    answered = client.post(
        f"{API}/episodes/{episode}/before",
        json={
            "constructed_response": answer,
            "response_time_ms": 6500,
            "visual": VISUAL,
            "learner_state_session_id": app_session,
        },
        headers=headers(learner, key="before"),
    )

    assert answered.status_code == 200, answered.text
    session = next(app.dependency_overrides[get_db]())
    stored = SqlAlchemyLearnerSkillStateRepository(session).get(UUID(learner), "MAT-FRC")
    assert stored is not None
    assert stored.session_id == app_session
    assert stored.recommended_action in {
        "none",
        "monitor",
        "request_tutor_support",
        "request_reengagement_support",
        "collect_more_evidence",
    }


def test_an_invalid_camera_snapshot_never_rejects_the_answer() -> None:
    request = AnswerRequest.model_validate(
        {"option_id": "a", "visual": VISUAL | {"face_visibility_ratio": 1.5}}
    )

    assert request.visual is None
    assert request.option_id == "a"
