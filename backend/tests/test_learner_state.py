from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.learner_state.application.support_need import (
    StoredSupportNeedProvider,
    SupportNeedRequest,
    SupportNeedStatus,
)
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.main import app
from app.shared.database.session import get_db


def create_learner(client: TestClient) -> str:
    response = client.post(
        "/api/v1/learners",
        json={"grade": 5, "preferred_language": "si"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def learner_state_payload(learner_id: str, window_id: int = 1) -> dict:
    return {
        "session_id": "learner-state-test-session",
        "learner_id": learner_id,
        "window_id": window_id,
        "skill_id": "MAT-FRC",
        "timestamp": "2026-10-13T09:45:00+05:30",
        "visual": {
            "mean_eye_openness": 0.27,
            "std_eye_openness": 0.04,
            "mean_gaze_ratio": 0.52,
            "std_gaze_ratio": 0.08,
            "mean_pitch": 8.0,
            "mean_yaw": 5.0,
            "mean_roll": 3.0,
            "mean_abs_pitch": 8.0,
            "mean_abs_yaw": 5.0,
            "mean_abs_roll": 3.0,
            "face_visibility_ratio": 0.95,
        },
        "behaviour": {
            "correct": 0.0,
            "bottom_hint": None,
            "hint_count": 3.0,
            "attempt_count": 4.0,
            "ms_first_response": 15000.0,
            "overlap_time": 25000.0,
            "first_action": 0.0,
            "position": 1.0,
            "original": 1.0,
        },
        "task_progress": 0.3,
    }


def test_evaluate_learner_state_and_reject_duplicate_window(
    client: TestClient,
) -> None:
    learner_id = create_learner(client)
    payload = learner_state_payload(learner_id)

    response = client.post(
        "/api/v1/learner-state",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["session_id"] == payload["session_id"]
    assert body["learner_id"] == learner_id
    assert body["window_id"] == 1
    assert body["skill_id"] == "MAT-FRC"

    assert "visual_probability" in body["confusion"]
    assert "behavior_probability" in body["confusion"]
    assert "fused_evidence" in body["confusion"]
    assert "confidence" in body["confusion"]

    assert "visual_probability" in body["disengagement"]
    assert "behavior_probability" in body["disengagement"]
    assert "fused_evidence" in body["disengagement"]
    assert "confidence" in body["disengagement"]

    for signal in ("confusion", "disengagement"):
        assert 0.0 <= body[signal]["temporal_score"] <= 1.0
        assert 0.0 <= body[signal]["average_confidence"] <= 1.0
        assert body[signal]["persistent_count"] in {0, 1}

    assert body["recommended_action"] in {
        "none",
        "monitor",
        "request_tutor_support",
        "request_reengagement_support",
        "collect_more_evidence",
    }

    duplicate = client.post(
        "/api/v1/learner-state",
        json=payload,
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "window_id must increase within a learner session"
    }


def test_window_ids_may_skip_values(client: TestClient) -> None:
    learner_id = create_learner(client)

    first = client.post("/api/v1/learner-state", json=learner_state_payload(learner_id, 1))
    later = client.post("/api/v1/learner-state", json=learner_state_payload(learner_id, 5))

    assert first.status_code == 200
    assert later.status_code == 200
    assert later.json()["window_id"] == 5


def test_out_of_range_features_are_rejected(client: TestClient) -> None:
    payload = learner_state_payload(create_learner(client))
    payload["visual"]["face_visibility_ratio"] = 1.4

    response = client.post("/api/v1/learner-state", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "visual",
        "face_visibility_ratio",
    ]


def test_unknown_learner_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/learner-state",
        json=learner_state_payload(str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Learner not found"}


def test_skill_id_is_required(client: TestClient) -> None:
    payload = learner_state_payload(create_learner(client))
    del payload["skill_id"]

    response = client.post("/api/v1/learner-state", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "skill_id"]


def test_latest_state_is_stored_per_skill(client: TestClient) -> None:
    learner_id = create_learner(client)
    first = learner_state_payload(learner_id, 1)
    second = learner_state_payload(learner_id, 2)
    second["skill_id"] = "LAN-CMP"

    first_response = client.post("/api/v1/learner-state", json=first)
    client.post("/api/v1/learner-state", json=second)

    session = next(app.dependency_overrides[get_db]())
    provider = StoredSupportNeedProvider(SqlAlchemyLearnerSkillStateRepository(session))

    stored = provider.get_support_need(
        SupportNeedRequest(learner_id=UUID(learner_id), skill_id="MAT-FRC")
    )
    other_skill = provider.get_support_need(
        SupportNeedRequest(learner_id=UUID(learner_id), skill_id="LAN-CMP")
    )
    unseen_skill = provider.get_support_need(
        SupportNeedRequest(learner_id=UUID(learner_id), skill_id="ENV-PLT")
    )

    confusion = first_response.json()["confusion"]
    assert confusion["state"] != "uncertain"
    assert stored.status is SupportNeedStatus.AVAILABLE
    assert stored.support_need == confusion["temporal_score"]
    assert other_skill.status is SupportNeedStatus.AVAILABLE
    assert unseen_skill.status is SupportNeedStatus.NOT_FOUND
