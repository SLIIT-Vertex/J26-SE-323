"""Pilot session API. Adult-tester auth is a development stub."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION, PILOT_SKILL, build_session_play
from app.gamification.api.router import get_play_service
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.loader import load_pilot_content_package
from app.main import app

LEARNER = UUID("00000000-0000-4000-8000-000000000201")
OTHER = UUID("00000000-0000-4000-8000-000000000299")
_CATALOG = PilotContentCatalog(load_pilot_content_package(allow_draft=True))


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


def _correct_option(item_id: str) -> str:
    item = _CATALOG.item(item_id)
    return item.correct_option_id


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


def test_manifest_hides_the_answer_key_until_support_is_decided(api: TestClient) -> None:
    created, _payload = _create(api)
    session_id = created["session_id"]
    activity = api.post(
        f"/api/v1/game-sessions/{session_id}/next-activity",
        headers=_headers(key="next-1"),
        json={"skill_id": PILOT_SKILL, "device_capabilities": ["choice_quest", "build_manipulate"]},
    )
    assert activity.status_code == 200, activity.text
    body = activity.json()
    manifest = body["manifest"]
    encoded = str(body)
    assert "correct_option_id" not in encoded
    assert "misconception" not in encoded
    assert body["support"] is None
    assert manifest["options"]
    assert all("text" in option and "option_id" in option for option in manifest["options"])
    assert set(manifest) == {"item_id", "question_text", "language", "template_key", "options"}


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
def test_adult_tester_completes_one_episode(api: TestClient, mode: str) -> None:
    created, _payload = _create(api, f"play-{mode}")
    session_id = created["session_id"]
    activity = api.post(
        f"/api/v1/game-sessions/{session_id}/next-activity",
        headers=_headers(key=f"next-{mode}", **{"X-Decision-Mode": mode}),
        json={"skill_id": PILOT_SKILL, "device_capabilities": ["choice_quest", "build_manipulate"]},
    )
    assert activity.status_code == 200, activity.text
    opened = activity.json()
    episode_id = opened["episode_id"]
    baseline_item = opened["manifest"]["item_id"]
    answered = api.post(
        f"/api/v1/game-sessions/{session_id}/responses",
        headers=_headers(key=f"base-{mode}"),
        json={
            "episode_id": episode_id,
            "selected_option_id": "A",
            "response_time_ms": 5000,
        },
    )
    assert answered.status_code == 200, answered.text
    support = answered.json()
    assert support["next_step"] == "present_support"
    assert support["support"]["steps"]
    assert "misconception" not in str(support).lower()
    completed = api.post(
        f"/api/v1/adaptive-episodes/{episode_id}/support/complete",
        headers=_headers(key=f"done-{mode}"),
        json={"duration_ms": 4000, "step_count": 2},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["next_step"] == "continue"
    withdrawn = api.post(
        f"/api/v1/adaptive-episodes/{episode_id}/support/withdraw",
        headers=_headers(key=f"withdraw-{mode}"),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    verification = withdrawn.json()
    assert verification["next_step"] == "present_verification"
    assert verification["support"] is None
    assert verification["manifest"]["item_id"] != baseline_item
    assert "correct_option_id" not in str(verification)
    verified = api.post(
        f"/api/v1/game-sessions/{session_id}/responses",
        headers=_headers(key=f"verify-{mode}"),
        json={
            "episode_id": episode_id,
            "selected_option_id": _correct_option(verification["manifest"]["item_id"]),
            "response_time_ms": 4000,
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["next_step"] == "finish"
    assert "independence_gain" not in verified.json()
    reconstruction = api.get(
        f"/api/v1/adaptive-episodes/{episode_id}/reconstruction",
        headers=_headers(role="researcher"),
    )
    assert reconstruction.status_code == 200, reconstruction.text
    evidence = reconstruction.json()
    assert evidence["beliefs"]
    assert evidence["candidates"]
    assert evidence["delivered_scaffold_id"]
    assert evidence["baseline_score"] == 0
    assert evidence["verification_score"] == 1
    assert evidence["independence_gain"] == 1
    assert evidence["validity"] == "valid"
    assert "selected_option" not in str(evidence)
