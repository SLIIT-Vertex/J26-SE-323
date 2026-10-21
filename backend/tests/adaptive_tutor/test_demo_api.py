from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.adaptive_tutor.api.router import get_demo_session_store
from app.adaptive_tutor.infrastructure.demo_sessions import SyntheticDemoSessionStore
from app.config import Settings, get_settings
from app.main import app

BASE = "/api/v1/adaptive-tutor/demo"
NOTICE = "SYNTHETIC RESEARCH DEMONSTRATION — NOT REAL LEARNER DATA OR VALIDATED LLM OUTPUT."


@pytest.fixture
def demo_client() -> Generator[TestClient, None, None]:
    previous = app.dependency_overrides.copy()
    store = SyntheticDemoSessionStore(lifetime=timedelta(minutes=5))
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        tutor_api_mode="synthetic-demo",
        tutor_demo_access_key="research-only",
    )
    app.dependency_overrides[get_demo_session_store] = lambda: store
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def headers(*, key: str = "research-only", token: str | None = None) -> dict[str, str]:
    result = {"X-Tutor-Demo-Key": key}
    if token:
        result["X-Tutor-Session-Token"] = token
    return result


def start(client: TestClient, scenario_id: str) -> dict[str, object]:
    response = client.post(
        f"{BASE}/sessions",
        json={"scenario_id": scenario_id},
        headers=headers(),
    )
    assert response.status_code == 201
    return response.json()


def submit(client: TestClient, session: dict[str, object], message: str = "Help me learn."):
    return client.post(
        f"{BASE}/sessions/{session['session_id']}/questions",
        json={"student_message": message, "response_language": "en"},
        headers=headers(token=str(session["session_token"])),
    )


def test_demo_access_is_deny_by_default_and_internal_shadow_is_not_exposed(
    demo_client: TestClient,
) -> None:
    assert demo_client.get(f"{BASE}/scenarios").status_code == 401
    assert demo_client.get(f"{BASE}/scenarios", headers=headers(key="wrong")).status_code == 401
    assert (
        "/api/v1/adaptive-tutor/internal-shadow"
        not in demo_client.get("/openapi.json").json()["paths"]
    )


def test_server_owned_session_and_interaction_are_isolated(demo_client: TestClient) -> None:
    first = start(demo_client, "L1")
    second = start(demo_client, "L2")

    response = submit(demo_client, first)
    body = response.json()
    assert response.status_code == 200
    assert body["session_id"] == first["session_id"]
    assert body["interaction_sequence"] == 1
    assert body["interaction_id"]
    assert body["delivery_authorized"] is False
    assert "response_text" not in body
    assert (
        submit(
            demo_client,
            {"session_id": first["session_id"], "session_token": second["session_token"]},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    ("scenario_id", "level"),
    [(f"L{level}", f"L{level}") for level in range(7)],
)
def test_synthetic_l0_to_l6_show_only_authored_examples(
    demo_client: TestClient,
    scenario_id: str,
    level: str,
) -> None:
    session = start(demo_client, scenario_id)
    response = submit(demo_client, session)
    body = response.json()

    assert response.status_code == 200
    assert body["assistance_level"] == level
    assert body["status"] == "SIMULATED_VERIFICATION_PASS"
    assert body["demonstration_notice"] == NOTICE
    assert body["demonstration_explanation"]
    assert body["verification_simulated"] is True
    assert body["execution_origin"] == "SYNTHETIC"
    assert "response_text" not in body


@pytest.mark.parametrize(
    ("scenario_id", "status"),
    [
        ("L6_BLOCKED_NO_APPROVED_CURRICULUM", "CURRICULUM_UNAVAILABLE"),
        ("VERIFICATION_FAILED", "VERIFICATION_FAILED"),
        ("VERIFICATION_INDETERMINATE", "VERIFICATION_INDETERMINATE"),
        ("MISSING_CONTEXT", "CONTEXT_NOT_READY"),
        ("SKILL_MAPPER_ABSTENTION", "CLARIFICATION_REQUIRED"),
        ("PROVIDER_FAILURE", "GENERATION_FAILED"),
    ],
)
def test_blocked_scenarios_return_typed_metadata_without_text(
    demo_client: TestClient,
    scenario_id: str,
    status: str,
) -> None:
    body = submit(demo_client, start(demo_client, scenario_id)).json()

    assert body["status"] == status
    assert body["delivery_authorized"] is False
    assert "demonstration_explanation" not in body
    assert "response_text" not in body


def test_history_contains_safe_metadata_and_reset_revokes_session(demo_client: TestClient) -> None:
    session = start(demo_client, "L3")
    assert submit(demo_client, session).status_code == 200
    session_headers = headers(token=str(session["session_token"]))
    history = demo_client.get(
        f"{BASE}/sessions/{session['session_id']}/history",
        headers=session_headers,
    )
    assert len(history.json()["interactions"]) == 1
    assert "student_message" not in history.text
    assert (
        demo_client.delete(
            f"{BASE}/sessions/{session['session_id']}", headers=session_headers
        ).status_code
        == 204
    )
    assert (
        demo_client.get(
            f"{BASE}/sessions/{session['session_id']}/history", headers=session_headers
        ).status_code
        == 404
    )


def test_client_cannot_supply_trusted_evidence_or_identity(demo_client: TestClient) -> None:
    session = start(demo_client, "L1")
    response = demo_client.post(
        f"{BASE}/sessions/{session['session_id']}/questions",
        json={
            "student_message": "Help.",
            "response_language": "en",
            "mastery": 1,
            "support_need": 0,
            "error_severity": 0,
            "assistance_level": "L6",
            "verification_simulated": False,
            "learner_id": "00000000-0000-4000-8000-000000000001",
            "interaction_id": "client-owned",
        },
        headers=headers(token=str(session["session_token"])),
    )
    assert response.status_code == 422
