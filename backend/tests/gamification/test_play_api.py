"""Pilot session API. Adult-tester auth is a development stub."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION, PILOT_SKILL, build_session_play
from app.gamification.api.router import get_play_service
from app.gamification.application.evaluation_protocol import load_frozen_protocol
from app.main import app

LEARNER = UUID("00000000-0000-4000-8000-000000000201")
OTHER = UUID("00000000-0000-4000-8000-000000000299")


@pytest.fixture
def api(client: TestClient) -> TestClient:
    service = build_session_play()
    app.dependency_overrides[get_play_service] = lambda: service
    return client


def _headers(
    learner: UUID = LEARNER, role: str = "learner", key: str | None = None, **extra: str
) -> dict[str, str]:
    headers = {
        "X-Dev-Principal": NOT_FOR_PRODUCTION,
        "X-Dev-Role": role,
        "X-Correlation-ID": "c6-test",
        **extra,
    }
    if role == "learner":
        headers["X-Learner-Id"] = str(learner)
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _body(client_session_id: UUID | None = None) -> dict[str, str]:
    return {
        "learner_id": str(LEARNER),
        "client_session_id": str(client_session_id or uuid4()),
        "language": "si",
    }


def _create(api: TestClient, key: str = "create-1") -> tuple[dict[str, object], dict[str, str]]:
    payload = _body()
    response = api.post("/api/v1/game-sessions", headers=_headers(key=key), json=payload)
    assert response.status_code == 200, response.text
    return response.json(), payload


def test_missing_dev_auth_is_rejected(api: TestClient) -> None:
    response = api.post("/api/v1/game-sessions", headers={"Idempotency-Key": "none"}, json=_body())
    assert response.status_code == 401
    assert response.json()["code"] == "DEV_AUTH_REQUIRED"
    assert response.headers["x-correlation-id"]


def test_idempotent_create_replays_and_rejects_a_different_body(api: TestClient) -> None:
    created, payload = _create(api, "same-key")
    replay = api.post("/api/v1/game-sessions", headers=_headers(key="same-key"), json=payload)
    assert replay.status_code == 200
    assert replay.json()["session_id"] == created["session_id"]
    changed = {**payload, "client_session_id": str(uuid4())}
    conflict = api.post("/api/v1/game-sessions", headers=_headers(key="same-key"), json=changed)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "DUPLICATE_IDEMPOTENCY_KEY"


def test_next_activity_does_not_serve_a_drafted_question(api: TestClient) -> None:
    created, _payload = _create(api)
    activity = api.post(
        f"/api/v1/game-sessions/{created['session_id']}/next-activity",
        headers=_headers(key="next-1"),
        json={"skill_id": PILOT_SKILL, "device_capabilities": ["choice_quest", "build_manipulate"]},
    )
    assert activity.status_code == 409, activity.text
    assert activity.json()["code"] == "CURRICULUM_RETRIEVAL_UNAVAILABLE"
    assert "question_text" not in activity.text


def test_cross_learner_access_and_researcher_reconstruction(api: TestClient) -> None:
    created, _payload = _create(api, "owned")
    session_id = created["session_id"]
    denied = api.post(
        f"/api/v1/game-sessions/{session_id}/next-activity",
        headers=_headers(learner=OTHER, key="other-next"),
        json={"skill_id": PILOT_SKILL},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "LEARNER_ACCESS_DENIED"
    missing = api.get(
        f"/api/v1/adaptive-episodes/{uuid4()}/reconstruction",
        headers=_headers(role="learner"),
    )
    assert missing.status_code == 403
    assert missing.json()["code"] == "RESEARCHER_ROLE_REQUIRED"


def test_sequence_conflict_accepts_nothing_and_bounds_the_batch(api: TestClient) -> None:
    created, _payload = _create(api, "events")
    session_id = created["session_id"]
    event = {
        "event_id": str(uuid4()),
        "sequence_no": 2,
        "event_type": "item_presented",
        "event_version": 1,
        "client_occurred_at": "2026-10-14T12:00:00Z",
        "payload": {"item_id": "shown"},
    }
    conflict = api.post(
        f"/api/v1/game-sessions/{session_id}/events:batch",
        headers=_headers(key="batch-gap"),
        json={"first_sequence_no": 2, "events": [event]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "SESSION_SEQUENCE_CONFLICT"
    pointer = {**event, "event_id": str(uuid4()), "sequence_no": 1, "payload": {"x": "1", "y": "2"}}
    accepted = api.post(
        f"/api/v1/game-sessions/{session_id}/events:batch",
        headers=_headers(key="batch-1"),
        json={"first_sequence_no": 1, "events": [pointer]},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {
        "accepted": 0,
        "duplicate": 0,
        "quarantined": 1,
        "expected_next_sequence": 2,
    }
    oversized = api.post(
        f"/api/v1/game-sessions/{session_id}/events:batch",
        headers=_headers(key="batch-big"),
        json={
            "first_sequence_no": 2,
            "events": [
                {
                    "event_id": str(uuid4()),
                    "sequence_no": index,
                    "event_type": "option_changed",
                    "event_version": 1,
                    "client_occurred_at": "2026-10-14T12:00:00Z",
                    "payload": {},
                }
                for index in range(2, 60)
            ],
        },
    )
    assert oversized.status_code == 422


def test_illegal_transition_is_a_state_conflict(api: TestClient) -> None:
    created, _payload = _create(api, "illegal")
    session_id = created["session_id"]
    early = api.post(
        f"/api/v1/game-sessions/{session_id}/responses",
        headers=_headers(key="too-soon"),
        json={"episode_id": str(uuid4()), "selected_option_id": "A", "response_time_ms": 1000},
    )
    assert early.status_code == 409
    assert early.json()["code"] == "EPISODE_STATE_CONFLICT"


def test_learned_mode_without_an_approved_artifact_is_not_ready(api: TestClient) -> None:
    created, _payload = _create(api, "learned")
    response = api.post(
        f"/api/v1/game-sessions/{created['session_id']}/next-activity",
        headers=_headers(key="learned-next", **{"X-Decision-Mode": "learned"}),
        json={"skill_id": PILOT_SKILL},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MODEL_NOT_READY"


@pytest.mark.parametrize("mode", ["performance_triggered_fixed", "shadow"])
def test_play_refuses_curriculum_questions_from_the_draft_package(
    api: TestClient, mode: str
) -> None:
    created, _payload = _create(api, f"play-{mode}")
    activity = api.post(
        f"/api/v1/game-sessions/{created['session_id']}/next-activity",
        headers=_headers(key=f"next-{mode}", **{"X-Decision-Mode": mode}),
        json={"skill_id": PILOT_SKILL, "device_capabilities": ["choice_quest", "build_manipulate"]},
    )
    assert activity.status_code == 409, activity.text
    assert activity.json()["code"] == "CURRICULUM_RETRIEVAL_UNAVAILABLE"


def test_assigned_arm_and_monitoring_are_researcher_operations(api: TestClient) -> None:
    protocol = load_frozen_protocol()
    learner = uuid4()
    body = {
        "experiment_id": str(uuid4()),
        "learner_id": str(learner),
        "seed": 3,
        "protocol_hash": protocol.digest,
    }
    denied = api.post(
        "/api/v1/experiments/assignments",
        headers=_headers(role="learner", key="assign-denied"),
        json=body,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "RESEARCHER_ROLE_REQUIRED"
    assigned = api.post(
        "/api/v1/experiments/assignments",
        headers=_headers(role="researcher", key="assign-1"),
        json=body,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["arm_key"] in {
        "baseline_performance_triggered",
        "proposed_misconception_ig_policy",
    }
    mismatch = api.post(
        "/api/v1/experiments/assignments",
        headers=_headers(role="researcher", key="assign-bad"),
        json={**body, "protocol_hash": "0" * 64},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "PROTOCOL_HASH_MISMATCH"
    created = api.post(
        "/api/v1/game-sessions",
        headers=_headers(learner=learner, key="assign-session"),
        json={
            "learner_id": str(learner),
            "client_session_id": str(uuid4()),
            "language": "si",
        },
    )
    assert created.status_code == 200, created.text
    activity = api.post(
        f"/api/v1/game-sessions/{created.json()['session_id']}/next-activity",
        headers=_headers(learner=learner, key="assign-next", **{"X-Decision-Mode": "learned"}),
        json={"skill_id": PILOT_SKILL},
    )
    assert activity.status_code == 409, activity.text
    assert activity.json()["code"] == "CURRICULUM_RETRIEVAL_UNAVAILABLE"
    counters = api.get("/api/v1/evaluation/monitoring", headers=_headers(role="researcher"))
    assert counters.status_code == 200, counters.text
    assert counters.json()["inputs"] == "in-process engineering counters"
    hidden = api.get("/api/v1/evaluation/monitoring", headers=_headers(role="learner"))
    assert hidden.status_code == 403
