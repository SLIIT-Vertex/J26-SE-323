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
from tests.gamification.helpers.support_loop_helpers import (
    finish_help,
    skip_watch_only_help,
    wrong_answer,
)

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
    assert support["scaffold_type"] == flow.reconstruct(episode)["state"]["model2"]["support_order"][0]
    # The help is built from the server's trace of the failed item; the phone never receives it.
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    assert flow._area_flows["G5-AREA-MAT-08"].support_solution(before)["correct_response"]["working_steps"]
    assert "working_steps" not in str(support)
    help_done = finish_help(flow, episode, supported)
    flow.withdraw_support(episode, **help_done, request_id=uuid4(), all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-division-support")
    after = flow.present_after(episode, idempotency_key="present-division-after")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    state = flow.reconstruct(episode)["state"]
    wrong_after = _make_wrong(_bound_response(state, "unsupported_after"))
    final = flow.submit_after(episode, option_id=None, constructed_response=wrong_after, response_time_ms=750, idempotency_key="answer-division-after")
    # Measured and complete; the child is then given the next help on the same episode id.
    assert final["episode_id"] == opened["episode_id"]
    assert final["status"] == "support_active"
    state = flow.reconstruct(episode)["state"]
    assert state["status"] == "completed"
    assert state["withdrawal"]["answer_revealing_state_cleared"] is True
    assert final["support"]["scaffold_type"] not in state["support_loop"]["types_used"]
    session.close()


def test_worked_example_round_shows_a_full_trace_of_a_different_problem():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=RecordingEvidencePublisher())
    game_flow = flow._area_flows["G5-AREA-MAT-08"]
    # Watching the visual demonstration goes straight to withdrawal; this test walks the answerable rounds.
    skip_watch_only_help(game_flow)
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="baseline", environment="test", allow_draft=True, area_id="G5-AREA-MAT-08", atomic_skill_id="G5-MAT-DIV-REMAINDER-01", idempotency_key="open-worked")
    episode = UUID(opened["episode_id"])
    state = flow.reconstruct(episode)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    response = flow.submit_before(episode, option_id=None, constructed_response=_make_wrong(_bound_response(state, "unsupported_before")), response_time_ms=600, interaction_summary=_summary(1), idempotency_key="wrong-worked")

    # Wrong inside every help until the server opens its worked example.
    for step in range(8):
        if response["support"]["scaffold_type"] == "worked_parallel_example":
            break
        if response["support"]["game_manifest"]["stage_kind"] == "view":
            # A visual demonstration is watched, not answered.
            response = flow.complete_support(episode, duration_ms=100, steps_viewed=1, manifest_revision_id=response["support"]["game_manifest"]["revision_id"], grouped_count=0, group_sizes=(0, 0), interaction_summary={"completed": True}, idempotency_key=f"watch-help-{step}")
            continue
        current = game_flow._support_rounds.current_item(flow.reconstruct(episode)["state"])
        response = flow.submit_supported(episode, constructed_response=wrong_answer(game_flow, current), response_time_ms=100, interaction_summary={}, idempotency_key=f"wrong-help-{step}")
    worked = response["support"]["game_manifest"]["worked_example"]
    assert response["support_round"]["english_tag_key"] == "WORKED_EXAMPLE"
    assert worked["revision_id"] != before["revision_id"]
    assert worked["solution"]["working_steps"]
    assert worked["solution"]["final_remainder"] < worked["solution"]["divisor"]
    assert worked["solution"] != game_flow.support_solution(before)["correct_response"]
    session.close()
