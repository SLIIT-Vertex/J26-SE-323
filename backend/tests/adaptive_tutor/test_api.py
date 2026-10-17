import json
import socket
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.adaptive_tutor.api.router import get_tutor_orchestrator_factory
from app.adaptive_tutor.application import (
    ContextInput,
    ContextIssue,
    ContextIssueKind,
    ContextReadinessReason,
    TutorWorkflowResult,
    TutorWorkflowStatus,
    VerificationOutcome,
)
from app.adaptive_tutor.application.orchestration import SYNTHETIC_DEMO_NOTICE
from app.adaptive_tutor.domain import AssistanceLevel
from app.config import Settings, get_settings
from app.curriculum.application import CurriculumRetrievalStatus
from app.main import app
from app.shared.database.session import get_db

PATH = "/api/v1/adaptive-tutor/responses"
LEARNERS = {
    "L0": "00000000-0000-4000-8000-000000000001",
    "L3": "00000000-0000-4000-8000-000000000006",
    "L6": "00000000-0000-4000-8000-000000000012",
}


@pytest.fixture
def synthetic_client() -> TestClient:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        tutor_api_mode="synthetic-demo",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def payload(
    learner_id: str = LEARNERS["L0"],
    student_message: str = "Help me understand this fractions problem.",
    **changes: object,
) -> dict[str, object]:
    request: dict[str, object] = {
        "learner_id": learner_id,
        "student_message": student_message,
        "response_language": "en",
        "conversation_context": [],
    }
    request.update(changes)
    return request


def synthetic_result(
    workflow_status: TutorWorkflowStatus,
    **changes: object,
) -> TutorWorkflowResult:
    values: dict[str, object] = {
        "status": workflow_status,
        "safe_message": "Synthetic workflow outcome.",
        "execution_origin": "SYNTHETIC",
        "demonstration_notice": SYNTHETIC_DEMO_NOTICE,
    }
    values.update(changes)
    return TutorWorkflowResult.model_validate(values)


@dataclass
class StubOrchestrator:
    result: TutorWorkflowResult

    def run(self, request: object) -> TutorWorkflowResult:
        return self.result


def override_result(result: TutorWorkflowResult) -> None:
    app.dependency_overrides[get_tutor_orchestrator_factory] = lambda: (
        lambda learner_id: StubOrchestrator(result)
    )


def test_endpoint_is_registered_with_typed_openapi_contracts(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][PATH]["post"]

    assert set(schema["paths"][PATH]) == {"post"}
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/TutorApiRequest"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/TutorApiResponse"
    )
    assert "synthetic-l0" in operation["requestBody"]["content"]["application/json"]["examples"]
    response_example = schema["components"]["schemas"]["TutorApiResponse"]["examples"][0]
    assert response_example["delivery_authorized"] is False
    assert "response_text" not in response_example


def test_existing_routes_remain_registered(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/health" in paths
    assert "/api/v1/learners" in paths
    assert "/api/v1/learner-state" in paths


def test_api_is_disabled_by_default_without_constructing_workflow(client: TestClient) -> None:
    app.dependency_overrides[get_tutor_orchestrator_factory] = lambda: (
        lambda learner_id: pytest.fail("disabled API constructed the workflow")
    )

    response = client.post(PATH, json=payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Adaptive Tutor API is disabled."}


@pytest.mark.parametrize(
    ("learner_key", "level"),
    [("L0", "L0"), ("L3", "L3"), ("L6", "L6")],
)
def test_controlled_synthetic_levels_remain_nondeliverable(
    synthetic_client: TestClient,
    learner_key: str,
    level: str,
) -> None:
    response = synthetic_client.post(PATH, json=payload(LEARNERS[learner_key]))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SIMULATED_VERIFICATION_PASS"
    assert body["assistance_level"] == level
    assert body["execution_mode"] == "synthetic-demo"
    assert body["execution_origin"] == "SYNTHETIC"
    assert body["verification_simulated"] is True
    assert body["delivery_authorized"] is False
    assert "response_text" not in body
    if level == "L6":
        assert body["curriculum_status"] == "FOUND"
        assert body["verification_evidence_provenance"]


def test_synthetic_mode_accepts_bounded_conversation_context(
    synthetic_client: TestClient,
) -> None:
    response = synthetic_client.post(
        PATH,
        json=payload(
            conversation_context=[
                {"role": "LEARNER", "message": "I tried halves."},
                {"role": "TUTOR", "message": "What did you notice?"},
            ],
            active_skill_id="MAT-FRC",
        ),
    )

    assert response.status_code == 200
    assert response.json()["confirmed_skill_id"] == "MAT-FRC"


@pytest.mark.parametrize(
    ("request_body", "location"),
    [
        (payload(learner_id="not-a-uuid"), "learner_id"),
        (payload(student_message="   "), "student_message"),
        (payload(student_message="x" * 4_001), "student_message"),
        (payload(response_language="x" * 17), "response_language"),
        (payload(active_skill_id="x" * 65), "active_skill_id"),
        (
            payload(
                conversation_context=[
                    {"role": "LEARNER", "message": str(index)} for index in range(9)
                ]
            ),
            "conversation_context",
        ),
        (
            payload(conversation_context=[{"role": "LEARNER", "message": "x" * 4_001}]),
            "body",
        ),
        (
            payload(conversation_context=[{"role": "INVALID", "message": "hello"}]),
            "role",
        ),
    ],
)
def test_invalid_requests_return_422(
    synthetic_client: TestClient,
    request_body: dict[str, object],
    location: str,
) -> None:
    response = synthetic_client.post(PATH, json=request_body)

    assert response.status_code == 422
    assert location in json.dumps(response.json()["detail"])


def test_unsupported_language_is_a_structured_workflow_outcome(
    synthetic_client: TestClient,
) -> None:
    response = synthetic_client.post(PATH, json=payload(response_language="fr"))

    assert response.status_code == 200
    assert response.json()["status"] == "UNSUPPORTED_LANGUAGE"
    assert response.json()["delivery_authorized"] is False


def test_unknown_synthetic_learner_is_rejected(synthetic_client: TestClient) -> None:
    response = synthetic_client.post(PATH, json=payload(str(uuid4())))

    assert response.status_code == 404
    assert response.json() == {"detail": "Synthetic learner fixture not found."}


@pytest.mark.parametrize(
    ("message", "workflow_status", "mapping_status"),
    [
        ("Can you help me?", "CLARIFICATION_REQUIRED", "AMBIGUOUS"),
        ("How do plants make food?", "NO_SUPPORTED_SKILL", "NO_MATCH"),
        ("Hello!", "NOT_SKILL_RELATED", "NOT_SKILL_RELATED"),
    ],
)
def test_controlled_nonmatch_mapping_outcomes(
    synthetic_client: TestClient,
    message: str,
    workflow_status: str,
    mapping_status: str,
) -> None:
    response = synthetic_client.post(PATH, json=payload(student_message=message))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == workflow_status
    assert body["skill_mapping_status"] == mapping_status
    assert body["delivery_authorized"] is False
    assert "response_text" not in body


def test_context_not_ready_exposes_only_safe_issue_codes(synthetic_client: TestClient) -> None:
    result = synthetic_result(
        TutorWorkflowStatus.CONTEXT_NOT_READY,
        context_issues=(
            ContextIssue(
                input=ContextInput.MASTERY,
                kind=ContextIssueKind.MISSING,
                reason=ContextReadinessReason.MASTERY_NOT_FOUND,
                message="A mastery estimate is unavailable.",
            ),
        ),
    )
    override_result(result)

    response = synthetic_client.post(PATH, json=payload())

    assert response.status_code == 200
    assert response.json()["context_readiness_status"] == "NOT_READY"
    assert response.json()["context_issue_codes"] == ["MASTERY_NOT_FOUND"]
    assert "response_text" not in response.json()


def test_l6_without_eligible_evidence_stops_before_generation(
    synthetic_client: TestClient,
) -> None:
    override_result(
        synthetic_result(
            TutorWorkflowStatus.CURRICULUM_UNAVAILABLE,
            assistance_level=AssistanceLevel.FULL_EXPLANATION,
            curriculum_status=CurriculumRetrievalStatus.NO_APPROVED_SOURCE,
        )
    )

    response = synthetic_client.post(PATH, json=payload(LEARNERS["L6"]))

    assert response.status_code == 200
    assert response.json()["status"] == "CURRICULUM_UNAVAILABLE"
    assert "generation_status" not in response.json()
    assert "response_text" not in response.json()


@pytest.mark.parametrize(
    ("workflow_status", "verification_outcome"),
    [
        (TutorWorkflowStatus.GENERATION_FAILED, None),
        (TutorWorkflowStatus.VERIFICATION_FAILED, VerificationOutcome.FAIL),
        (TutorWorkflowStatus.VERIFICATION_INDETERMINATE, VerificationOutcome.INDETERMINATE),
    ],
)
def test_failed_workflow_outcomes_are_safe_http_200_results(
    synthetic_client: TestClient,
    workflow_status: TutorWorkflowStatus,
    verification_outcome: VerificationOutcome | None,
) -> None:
    override_result(
        synthetic_result(
            workflow_status,
            verification_outcome=verification_outcome,
            verification_simulated=verification_outcome is not None,
        )
    )

    response = synthetic_client.post(PATH, json=payload())

    assert response.status_code == 200
    assert response.json()["status"] == workflow_status
    assert response.json()["delivery_authorized"] is False
    assert "response_text" not in response.json()


def test_public_projection_discards_a_hidden_rejected_draft(synthetic_client: TestClient) -> None:
    invalid_internal_result = synthetic_result(TutorWorkflowStatus.VERIFICATION_FAILED).model_copy(
        update={"response_text": "PRIVATE REJECTED DRAFT"}
    )
    override_result(invalid_internal_result)

    response = synthetic_client.post(PATH, json=payload())

    assert response.status_code == 200
    assert "PRIVATE REJECTED DRAFT" not in response.text
    assert "response_text" not in response.json()


def test_synthetic_endpoint_has_no_network_or_database_dependency(
    synthetic_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("external network attempted"),
    )

    def fail_database():
        pytest.fail("database dependency invoked")
        yield

    app.dependency_overrides[get_db] = fail_database

    response = synthetic_client.post(PATH, json=payload())

    assert response.status_code == 200
    assert response.json()["status"] == "SIMULATED_VERIFICATION_PASS"


def test_unexpected_factory_error_is_sanitized(synthetic_client: TestClient) -> None:
    def failing_factory(learner_id: UUID):
        raise RuntimeError("PRIVATE_PROVIDER_TOKEN=secret")

    app.dependency_overrides[get_tutor_orchestrator_factory] = lambda: failing_factory

    response = synthetic_client.post(PATH, json=payload())

    assert response.status_code == 500
    assert response.json() == {"detail": "Adaptive Tutor workflow could not be initialized safely."}
    assert "secret" not in response.text


def test_response_contains_provenance_without_provider_secrets(
    synthetic_client: TestClient,
) -> None:
    response = synthetic_client.post(PATH, json=payload())
    body = response.json()
    serialized = json.dumps(body).casefold()

    assert body["context_provenance"]
    assert body["demonstration_notice"] == SYNTHETIC_DEMO_NOTICE
    assert "api_key" not in serialized
    assert "gemini" not in serialized
    assert "provider_name" not in serialized
    assert "semantic_verifier_name" not in serialized
