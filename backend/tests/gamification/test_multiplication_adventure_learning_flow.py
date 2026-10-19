from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000746")


def test_one_episode_is_reused_and_support_starts_with_visual_guidance():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=RecordingEvidencePublisher(),
    )
    request = {
        "learner_id": LEARNER,
        "session_id": LEARNER,
        "grade": 5,
        "medium": "si",
        "condition": "proposed",
        "environment": "development",
        "allow_draft": True,
        "area_id": "G5-AREA-MAT-06",
        "atomic_skill_id": "G5-MAT-MUL-TABLE-01",
        "idempotency_key": "open-table",
    }
    opened = flow.open_episode(**request)
    again = flow.open_episode(**request)
    assert again["episode_id"] == opened["episode_id"]
    game = opened["manifest"]["game"]
    assert "product" not in game
    episode = UUID(opened["episode_id"])
    stored = flow.reconstruct(episode)["state"]["presentations"][0]
    answered = flow.submit_before(
        episode,
        option_id=None,
        constructed_response={
            "kind": "multiplication_fact",
            "multiplicand": game["multiplicand"],
            "multiplier": game["multiplier"],
            "product": 0,
            "presentation_id": stored["presentation_id"],
            "item_revision_id": stored["revision_id"],
            "interaction_version": "constructed-response-v1",
        },
        response_time_ms=None,
        interaction_summary={"attempt_count": 1, "digit_entry_count": 1},
        idempotency_key="answer-table",
    )
    assert answered["support"]["scaffold_type"] == "visual_guidance"
    assert answered["server_score"]["correct"] is False
    repeated = flow.submit_before(
        episode,
        option_id=None,
        constructed_response={
            "kind": "multiplication_fact",
            "multiplicand": game["multiplicand"],
            "multiplier": game["multiplier"],
            "product": 0,
            "presentation_id": stored["presentation_id"],
            "item_revision_id": stored["revision_id"],
            "interaction_version": "constructed-response-v1",
        },
        response_time_ms=None,
        interaction_summary={"attempt_count": 1, "digit_entry_count": 1},
        idempotency_key="answer-table",
    )
    assert repeated["episode_id"] == answered["episode_id"]
    session.close()
