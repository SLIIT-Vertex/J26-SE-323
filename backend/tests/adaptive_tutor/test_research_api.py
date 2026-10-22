from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.adaptive_tutor.api.router import get_research_tutor_service
from app.config import Settings, get_settings
from app.main import app

BASE = "/api/v1/adaptive-tutor/research"


@pytest.fixture
def research_client() -> Generator[TestClient, None, None]:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        tutor_api_mode="research-local",
        tutor_demo_access_key="synthetic-key",
        tutor_research_access_key="separate-research-key",
        tutor_researcher_id="00000000-0000-4000-8000-000000000222",
    )
    app.dependency_overrides[get_research_tutor_service] = lambda: SimpleNamespace(
        severity_policy_versions=("pp1-controlled-research-v1",)
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_research_status_requires_separate_research_authorization(
    research_client: TestClient,
) -> None:
    assert research_client.get(f"{BASE}/status").status_code == 401
    assert (
        research_client.get(
            f"{BASE}/status", headers={"X-Tutor-Demo-Key": "synthetic-key"}
        ).status_code
        == 401
    )
    response = research_client.get(
        f"{BASE}/status",
        headers={"X-Tutor-Research-Key": "separate-research-key"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "researcher_authorized": True,
        "execution_mode": "research-local",
        "child_delivery_enabled": False,
        # The form offers these, so a mistyped policy cannot be rejected after review.
        "severity_policy_versions": ["pp1-controlled-research-v1"],
    }


def test_research_contract_rejects_client_owned_evidence_fields(
    research_client: TestClient,
) -> None:
    response = research_client.post(
        f"{BASE}/sessions",
        headers={"X-Tutor-Research-Key": "separate-research-key"},
        json={
            "learner_id": "00000000-0000-4000-8000-000000000221",
            "mastery": 1,
            "support_need": 0,
            "assistance_level": "L6",
        },
    )
    assert response.status_code == 422


def test_research_path_is_disabled_outside_explicit_local_mode(
    research_client: TestClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        tutor_api_mode="synthetic-demo",
        tutor_research_access_key="separate-research-key",
        tutor_researcher_id="00000000-0000-4000-8000-000000000222",
    )
    response = research_client.get(
        f"{BASE}/status",
        headers={"X-Tutor-Research-Key": "separate-research-key"},
    )
    assert response.status_code == 503
