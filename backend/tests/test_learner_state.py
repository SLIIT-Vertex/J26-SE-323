from uuid import uuid4

from fastapi.testclient import TestClient


def test_evaluate_learner_state_and_reject_duplicate_window(
    client: TestClient,
) -> None:
    learner_id = str(uuid4())

    payload = {
        "session_id": "learner-state-test-session",
        "learner_id": learner_id,
        "window_id": 1,
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

    response = client.post(
        "/api/v1/learner-state",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["session_id"] == payload["session_id"]
    assert body["learner_id"] == learner_id
    assert body["window_id"] == 1

    assert "visual_probability" in body["confusion"]
    assert "behavior_probability" in body["confusion"]
    assert "fused_evidence" in body["confusion"]
    assert "confidence" in body["confusion"]

    assert "visual_probability" in body["disengagement"]
    assert "behavior_probability" in body["disengagement"]
    assert "fused_evidence" in body["disengagement"]
    assert "confidence" in body["disengagement"]

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