from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.division_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000758")


def _bound_response(state, role):
    item = next(row for row in state["presentations"] if row["role"] == role)
    response = correct_response(item["game_data"])
    response.update(presentation_id=item["presentation_id"], item_revision_id=item["revision_id"], interaction_version="constructed-response-v1")
    return response


def _make_wrong(response):
    wrong = {**response}
    wrong["working_steps"] = [{**step} for step in response["working_steps"]]
    wrong["working_steps"][0]["quotient_digit"] = (wrong["working_steps"][0]["quotient_digit"] + 1) % 10
    return wrong


def _summary(attempt_count):
    return {"move_count": 8, "correction_count": 1, "first_action_ms": 100, "active_time_ms": 700, "attempt_count": attempt_count, "working_cell_count": 10, "bring_down_count": 1}


def test_division_episode_reuses_one_id_and_withdraws_answer_state_before_retry():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="proposed", environment="test", allow_draft=True, area_id="G5-AREA-MAT-08", atomic_skill_id="G5-MAT-DIV-WRITTEN-01", idempotency_key="open-division")
    episode = UUID(opened["episode_id"])
    state = flow.reconstruct(episode)["state"]
    wrong = _make_wrong(_bound_response(state, "unsupported_before"))
    supported = flow.submit_before(episode, option_id=None, constructed_response=wrong, response_time_ms=800, interaction_summary=_summary(1), idempotency_key="wrong-division")
    assert supported["episode_id"] == opened["episode_id"]
    assert supported["server_score"]["feedback_step_index"] == 0
    support = supported["support"]
    assert support["scaffold_type"] == "visual_guidance"
    assert support["game_manifest"]["focus_step_index"] == 0
    assert support["game_manifest"]["worked_example"]["correct_response"]["working_steps"]
    manifest = support["game_manifest"]
    flow.complete_support(episode, duration_ms=1200, steps_viewed=3, manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": 3}, idempotency_key="complete-division-support")
    flow.withdraw_support(episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-division-support")
    after = flow.present_after(episode, idempotency_key="present-division-after")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    state = flow.reconstruct(episode)["state"]
    wrong_after = _make_wrong(_bound_response(state, "unsupported_after"))
    final = flow.submit_after(episode, option_id=None, constructed_response=wrong_after, response_time_ms=750, idempotency_key="answer-division-after")
    assert final["status"] == "completed"
    assert flow.reconstruct(episode)["state"]["withdrawal"]["answer_revealing_state_cleared"] is True
    session.close()


def test_second_failed_encounter_escalates_to_exact_worked_trace():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=RecordingEvidencePublisher())

    def fail_episode(key):
        opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="proposed", environment="test", allow_draft=True, area_id="G5-AREA-MAT-08", atomic_skill_id="G5-MAT-DIV-REMAINDER-01", idempotency_key=f"open-{key}")
        episode = UUID(opened["episode_id"])
        state = flow.reconstruct(episode)["state"]
        return episode, flow.submit_before(episode, option_id=None, constructed_response=_make_wrong(_bound_response(state, "unsupported_before")), response_time_ms=600, interaction_summary=_summary(1), idempotency_key=f"wrong-{key}")

    first_episode, first = fail_episode("one")
    support = first["support"]
    manifest = support["game_manifest"]
    flow.complete_support(first_episode, duration_ms=1000, steps_viewed=3, manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": 3}, idempotency_key="complete-one")
    flow.withdraw_support(first_episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-one")
    flow.present_after(first_episode, idempotency_key="present-one")
    state = flow.reconstruct(first_episode)["state"]
    flow.submit_after(first_episode, option_id=None, constructed_response=_make_wrong(_bound_response(state, "unsupported_after")), response_time_ms=600, idempotency_key="after-one")

    _, second = fail_episode("two")
    worked = second["support"]["game_manifest"]["worked_example"]
    assert second["support"]["scaffold_type"] == "worked_parallel_example"
    assert worked["mode"] == "exact_failed_activity"
    assert worked["correct_response"]["working_steps"]
    assert worked["correct_response"]["final_remainder"] < worked["correct_response"]["divisor"]
    session.close()
