"""Durable coordinator acceptance tests for the single draft skill."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.infrastructure.db.learning_flow_gateways import SqlAlchemyProbeGateway
from app.gamification.infrastructure.db.learning_flow_store import (
    SqlAlchemyLearningFlowStore,
)
from app.gamification.infrastructure.db.models import (
    LearnerEvidenceOutboxModel,
    LearningFlowAuditEventModel,
    LearningFlowEpisodeEventModel,
    LearningFlowEpisodeRunModel,
    LearningFlowIdempotencyReceiptModel,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000621")


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        now = datetime.now(UTC)
        session.add(
            LearnerModel(
                id=LEARNER,
                grade=5,
                preferred_language="si",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return engine


def _service(engine, *, probe=None, publisher=None):
    session = Session(engine)
    return (
        session,
        LearningFlowOrchestrator(
            SqlAlchemyLearningFlowStore(session),
            probe_gateway=probe or LocalProbeGateway(),
            evidence_publisher=publisher or RecordingEvidencePublisher(),
        ),
    )


def _open(service, *, condition="proposed", key="open"):
    return service.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        idempotency_key=key,
    )


def _complete_support(service, episode_id, *, key="support"):
    exposure = service.reconstruct(episode_id)["state"]["scaffold_exposure"]
    total = int(exposure["game_total_objects"])
    return service.complete_support(
        episode_id,
        duration_ms=900,
        steps_viewed=1,
        manifest_revision_id=exposure["game_manifest_revision_id"],
        grouped_count=total,
        group_sizes=(total // 2, total // 2),
        idempotency_key=key,
    )


def _withdraw_support(service, episode_id, *, key="withdraw"):
    exposure = service.reconstruct(episode_id)["state"]["scaffold_exposure"]
    return service.withdraw_support(
        episode_id,
        request_id=uuid4(),
        support_revision_id=exposure["revision_id"],
        manifest_revision_id=exposure["game_manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=key,
    )


def _complete(service, episode_id, *, after="C"):
    service.submit_before(episode_id, option_id="A", idempotency_key="before")
    _complete_support(service, episode_id)
    _withdraw_support(service, episode_id)
    presented = service.present_after(episode_id, idempotency_key="present-after")
    assert "correct_option_id" not in str(presented)
    return service.submit_after(episode_id, option_id=after, idempotency_key="after")


def test_proposed_episode_is_durable_replayable_and_authorizes_only_delayed_update(database):
    publisher = RecordingEvidencePublisher()
    session, service = _service(database, publisher=publisher)
    opened = _open(service)
    assert "correct_option_id" not in str(opened)
    episode_id = UUID(str(opened["episode_id"]))

    result = _complete(service, episode_id)

    assert result["status"] == "completed"
    assert result["raw_independence_gain"] == "1"
    assert result["percentage_point_value"] == "100"
    assert result["policy_update_status"] == "authorized_delayed"
    assert {record["assistance_state"] for record in publisher.records} == {"none"}
    for record in publisher.records:
        assert record["attempt_id"]
        assert record["correct"] in {True, False}
        assert record["difficulty"] == "easy"
        assert record["difficulty_source"] == "introductory"
        assert record["response_time_ms"] is None
        assert record["supported"] is False
        assert record["hint_count"] == 0
        assert record["universal_skill_id"] == "MAT-FRC"
        assert record["environment"] in {"development", "test"}
        assert record["model_ingestion_eligible"] is False
    reconstruction = service.reconstruct(episode_id)
    assert reconstruction["state_sha256"]
    gateways = reconstruction["state"]["external_gateways"]
    assert gateways["learner_state"]["status"] == "missing_safe_fallback"
    assert gateways["verified_tutor"]["status"] == "unavailable_authored_fallback"
    assert gateways["verified_tutor"]["probe_access"] is False
    assert gateways["knowledge_tracing"]["may_overwrite_independence_gain"] is False
    assert [event["sequence"] for event in reconstruction["events"]] == list(
        range(1, len(reconstruction["events"]) + 1)
    )
    manifest = service.export_manifest(episode_id)
    assert manifest["contains_item_text"] is False
    assert manifest["contains_answers"] is False
    first_hash = manifest["manifest_sha256"]
    session.close()

    restarted_session, restarted = _service(database)
    assert restarted.export_manifest(episode_id)["manifest_sha256"] == first_hash
    assert restarted.reconstruct(episode_id) == reconstruction
    restarted_session.close()


def test_baseline_valid_episode_never_authorizes_policy_learning(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service, condition="baseline")["episode_id"]))
    result = _complete(service, episode_id)
    assert result["validity"] == "valid"
    assert result["policy_update_status"] == "not_authorized_baseline"
    session.close()


def test_correct_unsupported_before_completes_without_scaffold_or_ig(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    result = service.submit_before(episode_id, option_id="B", idempotency_key="correct")
    assert result["status"] == "completed"
    assert result["validity"] == "not_applicable_no_support"
    assert result["raw_independence_gain"] is None
    assert result["policy_update_status"] == "not_authorized_no_support"
    session.close()


def test_production_unapproved_and_wrong_scope_fail_closed_without_rows(database):
    session, service = _service(database)
    for kwargs, code in (
        ({"environment": "production", "allow_draft": True}, "HUMAN_APPROVAL_REQUIRED"),
        ({"environment": "test", "allow_draft": False}, "HUMAN_APPROVAL_REQUIRED"),
        ({"environment": "test", "allow_draft": True, "grade": 4}, "GRADE5_SINHALA_REQUIRED"),
        ({"environment": "test", "allow_draft": True, "medium": "ta"}, "GRADE5_SINHALA_REQUIRED"),
    ):
        values = {
            "learner_id": LEARNER,
            "session_id": uuid4(),
            "grade": 5,
            "medium": "si",
            "condition": "baseline",
            "environment": "test",
            "allow_draft": True,
            "idempotency_key": str(uuid4()),
            **kwargs,
        }
        with pytest.raises(LearningFlowOrchestrationError, match=code):
            service.open_episode(**values)
    assert session.scalar(select(func.count()).select_from(LearningFlowEpisodeRunModel)) == 0
    session.close()


def test_idempotency_conflict_rolls_back_and_exact_retry_replays(database):
    session, service = _service(database)
    opened = _open(service)
    episode_id = UUID(str(opened["episode_id"]))
    first = service.submit_before(episode_id, option_id="A", idempotency_key="response")
    assert service.submit_before(
        episode_id, option_id="A", idempotency_key="response"
    ) == first
    with pytest.raises(LearningFlowOrchestrationError, match="IDEMPOTENCY_CONFLICT"):
        service.submit_before(episode_id, option_id="B", idempotency_key="response")
    assert session.scalar(select(func.count()).select_from(LearningFlowIdempotencyReceiptModel)) == 2
    session.close()


def test_invalid_answer_rolls_back_outbox_projection_and_receipt(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    before = service.reconstruct(episode_id)
    with pytest.raises(LearningFlowOrchestrationError, match="UNKNOWN_OPTION"):
        service.submit_before(episode_id, option_id="forged", idempotency_key="forged")
    assert service.reconstruct(episode_id) == before
    assert session.scalar(select(func.count()).select_from(LearnerEvidenceOutboxModel)) == 0
    assert session.get(LearningFlowIdempotencyReceiptModel, "forged") is None
    session.close()


def test_probe_contamination_invalidates_before_after_presentation(database):
    probe = LocalProbeGateway()
    session, service = _service(database, probe=probe)
    episode_id = UUID(str(_open(service)["episode_id"]))
    service.submit_before(episode_id, option_id="A", idempotency_key="b")
    _complete_support(service, episode_id, key="s")
    _withdraw_support(service, episode_id, key="w")
    state = service.reconstruct(episode_id)["state"]
    probe.contaminate(str(state["probe_reservation_id"]))
    result = service.present_after(episode_id, idempotency_key="p")
    assert result["status"] == "invalidated"
    assert result["policy_update_status"] == "not_authorized_invalid"
    assert result["exclusion_reasons"] == ["PRIOR_PROBE_EXPOSURE"]
    session.close()


def test_support_must_be_completed_and_withdrawn_before_after_probe(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    service.submit_before(episode_id, option_id="A", idempotency_key="b")
    with pytest.raises(LearningFlowOrchestrationError, match="EPISODE_STATE_CONFLICT"):
        service.present_after(episode_id, idempotency_key="too-soon")
    _complete_support(service, episode_id, key="s")
    with pytest.raises(LearningFlowOrchestrationError, match="EPISODE_STATE_CONFLICT"):
        service.present_after(episode_id, idempotency_key="still-too-soon")
    session.close()


def test_support_completion_and_withdrawal_proofs_are_revision_bound(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    service.submit_before(episode_id, option_id="A", idempotency_key="b-proof")
    with pytest.raises(LearningFlowOrchestrationError, match="INVALID_SUPPORT_COMPLETION"):
        service.complete_support(
            episode_id,
            duration_ms=1,
            steps_viewed=1,
            manifest_revision_id="stale-revision",
            grouped_count=6,
            group_sizes=(5, 1),
            idempotency_key="bad-completion-proof",
        )
    _complete_support(service, episode_id, key="good-completion-proof")
    with pytest.raises(
        LearningFlowOrchestrationError, match="INVALID_WITHDRAWAL_ACKNOWLEDGEMENT"
    ):
        service.withdraw_support(
            episode_id,
            request_id=uuid4(),
            support_revision_id="stale-revision",
            manifest_revision_id="stale-revision",
            all_support_removed=True,
            answer_revealing_state_cleared=True,
            input_handlers_cleared=True,
            idempotency_key="bad-withdrawal-proof",
        )
    _withdraw_support(service, episode_id, key="good-withdrawal-proof")
    withdrawal = service.reconstruct(episode_id)["state"]["withdrawal"]
    assert withdrawal["request_id"]
    assert withdrawal["input_handlers_cleared"] is True
    session.close()


def test_offline_batch_duplicate_gap_version_pii_and_bounds(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    event_id = uuid4()
    event = {"event_id": str(event_id), "sequence": 1, "version": 1, "payload": {"tap": True}}
    accepted = service.ingest_telemetry(
        episode_id,
        batch_id=uuid4(),
        first_sequence=1,
        events=(event,),
        idempotency_key="telemetry-1",
    )
    assert accepted["accepted"] == 1
    duplicate = service.ingest_telemetry(
        episode_id,
        batch_id=uuid4(),
        first_sequence=1,
        events=(event,),
        idempotency_key="telemetry-2",
    )
    assert duplicate["duplicates"] == 1
    with pytest.raises(LearningFlowOrchestrationError, match="CLIENT_SEQUENCE_GAP"):
        service.ingest_telemetry(
            episode_id,
            batch_id=uuid4(),
            first_sequence=3,
            events=({**event, "event_id": str(uuid4()), "sequence": 3},),
            idempotency_key="gap",
        )
    with pytest.raises(LearningFlowOrchestrationError, match="PII_OR_ANSWER_DATA_REJECTED"):
        service.ingest_telemetry(
            episode_id,
            batch_id=uuid4(),
            first_sequence=2,
            events=(
                {
                    "event_id": str(uuid4()),
                    "sequence": 2,
                    "version": 1,
                    "payload": {"answer": "B"},
                },
            ),
            idempotency_key="pii",
        )
    session.close()


def test_invalidated_episode_has_no_update_and_audit_is_persisted(database):
    session, service = _service(database)
    episode_id = UUID(str(_open(service)["episode_id"]))
    result = service.invalidate(
        episode_id, reason="INTERRUPTED_OR_INCOMPLETE", idempotency_key="invalidate"
    )
    assert result["policy_update_status"] == "not_authorized_invalid"
    assert result["reward"] is None
    assert session.scalar(select(func.count()).select_from(LearningFlowAuditEventModel)) == 2
    assert session.scalar(select(func.count()).select_from(LearningFlowEpisodeEventModel)) == 2
    session.close()


def test_sql_probe_reservation_survives_restart_and_blocks_cross_component_reuse(database):
    first_session = Session(database)
    first = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(first_session),
        probe_gateway=SqlAlchemyProbeGateway(first_session),
        evidence_publisher=RecordingEvidencePublisher(),
    )
    opened = _open(first, key="durable-open")
    episode_id = UUID(str(opened["episode_id"]))
    first.submit_before(episode_id, option_id="A", idempotency_key="durable-before")
    _complete_support(first, episode_id, key="durable-support")
    _withdraw_support(first, episode_id, key="durable-withdraw")
    first_session.close()

    second_session = Session(database)
    restarted = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(second_session),
        probe_gateway=SqlAlchemyProbeGateway(second_session),
        evidence_publisher=RecordingEvidencePublisher(),
    )
    assert restarted.present_after(episode_id, idempotency_key="durable-present")[
        "status"
    ] == "after_presented"
    with pytest.raises(LearningFlowOrchestrationError, match="PROBE_ALREADY_RESERVED_OR_EXPOSED"):
        _open(restarted, key="cross-component-reuse")
    second_session.close()


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
def test_development_http_slice_is_durable_authorized_and_object_scoped(
    client: TestClient,
    condition: str,
) -> None:
    learner = client.post(
        "/api/v1/learners", json={"grade": 5, "preferred_language": "si"}
    ).json()
    learner_id = learner["id"]

    def headers(key: str, *, role: str = "learner", subject: str = learner_id):
        values = {
            "X-Dev-Principal": "NOT_FOR_PRODUCTION",
            "X-Dev-Role": role,
            "Idempotency-Key": key,
        }
        if role == "learner":
            values["X-Learner-Id"] = subject
        return values

    opened = client.post(
        "/api/v1/development/learning-flow/episodes",
        headers=headers("http-open"),
        json={
            "learner_id": learner_id,
            "session_id": str(uuid4()),
            "grade": 5,
            "medium": "si",
            "condition": condition,
            "environment": "test",
            "allow_draft": True,
        },
    )
    assert opened.status_code == 200, opened.text
    episode_id = opened.json()["episode_id"]
    denied = client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/before",
        headers=headers("wrong-owner", subject=str(uuid4())),
        json={"option_id": "A"},
    )
    assert denied.status_code == 404
    supported = client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/before",
        headers=headers("http-before"),
        json={"option_id": "A"},
    )
    assert supported.status_code == 200
    support_revision = supported.json()["support"]["revision_id"]
    assert client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/support/complete",
        headers=headers("http-support"),
        json={
            "duration_ms": 3,
            "steps_viewed": 1,
            "manifest_revision_id": support_revision,
            "grouped_count": 6,
            "group_sizes": [3, 3],
        },
    ).status_code == 200
    assert client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/support/withdraw",
        headers=headers("http-withdraw"),
        json={
            "request_id": str(uuid4()),
            "support_revision_id": support_revision,
            "manifest_revision_id": support_revision,
            "all_support_removed": True,
            "answer_revealing_state_cleared": True,
            "input_handlers_cleared": True,
        },
    ).status_code == 200
    assert client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/after/present",
        headers=headers("http-present"),
    ).status_code == 200
    completed = client.post(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/after",
        headers=headers("http-after"),
        json={"option_id": "C"},
    )
    assert completed.status_code == 200, completed.text
    child_payload = completed.json()
    assert child_payload["status"] == "completed"
    assert child_payload["reward"] == {"points": 1, "reason": "episode_complete"}
    for research_field in (
        "raw_independence_gain",
        "percentage_point_value",
        "policy_update_status",
        "exclusion_reasons",
        "validity",
    ):
        assert research_field not in child_payload
    reconstruction = client.get(
        f"/api/v1/development/learning-flow/episodes/{episode_id}/reconstruction",
        headers=headers("unused", role="researcher"),
    )
    assert reconstruction.status_code == 200
    assert "correct_option_id" not in reconstruction.text
    missing = client.get(
        f"/api/v1/development/learning-flow/episodes/{uuid4()}/reconstruction",
        headers=headers("unused", role="researcher"),
    )
    assert missing.status_code == 404
