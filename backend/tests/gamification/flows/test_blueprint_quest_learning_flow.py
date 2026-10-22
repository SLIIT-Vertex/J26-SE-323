from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.blueprint_quest import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import finish_help

LEARNER=UUID("00000000-0000-4000-8000-000000000814")
@pytest.mark.parametrize("condition",["baseline","proposed"])
@pytest.mark.parametrize("skill",["G5-ENG-PLACE-VOCAB-01","G5-ENG-PLACE-GROUP-02","G5-ENG-PLACE-NAME-03"])
def test_lifecycle(condition,skill):
    engine=create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(engine);s=Session(engine);now=datetime.now(UTC);s.add(LearnerModel(id=LEARNER,grade=5,preferred_language="si",created_at=now,updated_at=now));s.commit();p=RecordingEvidencePublisher();f=LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(s),probe_gateway=LocalProbeGateway(),evidence_publisher=p);key=skill[-2:]
    opened=f.open_episode(learner_id=LEARNER,session_id=uuid4(),grade=5,medium="si",condition=condition,environment="test",allow_draft=True,area_id="G5-AREA-ENG-14",atomic_skill_id=skill,idempotency_key=f"o-{condition}-{key}");e=UUID(opened["episode_id"]);before=next(x for x in f.reconstruct(e)["state"]["presentations"] if x["role"]=="unsupported_before");wrong=correct_response(before["game_data"])
    if "placements" in wrong:
        rows=wrong["placements"];target="scene_token" if "scene_token" in rows[0] else "heading_token";other=next(i for i in range(1,len(rows)) if rows[i][target]!=rows[0][target]);rows[0][target],rows[other][target]=rows[other][target],rows[0][target]
    else: wrong["ordered_chunk_tokens"].reverse()
    wrong.update(presentation_id=before["presentation_id"],item_revision_id=before["revision_id"],interaction_version="constructed-response-v1");summary={"move_count":3,"correction_count":0,"first_action_ms":1,"active_time_ms":100,"attempt_count":1,"invalid_drop_count":0,"tap_alternative_used":True};supported=f.submit_before(e,option_id=None,constructed_response=wrong,response_time_ms=100,interaction_summary=summary,idempotency_key=f"b-{condition}-{key}")
    help_done = finish_help(f, e, supported);f.withdraw_support(e,**help_done,request_id=uuid4(),all_support_removed=True,answer_revealing_state_cleared=True,input_handlers_cleared=True,idempotency_key=f"w-{condition}-{key}");after=f.present_after(e,idempotency_key=f"p-{condition}-{key}");item=next(x for x in f.reconstruct(e)["state"]["presentations"] if x["role"]=="unsupported_after");answer=correct_response(item["game_data"]);answer.update(presentation_id=after["manifest"]["presentation_id"],item_revision_id=after["manifest"]["revision_id"],interaction_version="constructed-response-v1");result=f.submit_after(e,option_id=None,constructed_response=answer,response_time_ms=100,idempotency_key=f"a-{condition}-{key}");state=f.reconstruct(e)["state"];assert result["status"]=="completed" and state["model1"] and state["model2"] and state["withdrawal"]["input_handlers_cleared"] and p.records;s.close()
