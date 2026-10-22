"""Shared drivers for multi-help episodes in tests: answers built from the server's own solution."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.demo_seed import answers
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

MATHEMATICS_AREAS = {
    "G5-AREA-MAT-01": "NumberWorldFlow",
    "G5-AREA-MAT-02": "AdditionAdventureFlow",
    "G5-AREA-MAT-03": "NumberPatternsFlow",
    "G5-AREA-MAT-04": "SubtractionAdventureFlow",
    "G5-AREA-MAT-05": "FractionAdventureFlow",
    "G5-AREA-MAT-06": "MultiplicationAdventureFlow",
    "G5-AREA-MAT-07": "TimeAdventureFlow",
    "G5-AREA-MAT-08": "DivisionAdventureFlow",
    "G5-AREA-MAT-09": "DistanceAdventureFlow",
    "G5-AREA-MAT-10": "MoneyAdventureFlow",
    "G5-AREA-MAT-11": "CapacityAdventureFlow",
    "G5-AREA-MAT-12": "MassAdventureFlow",
    "G5-AREA-MAT-13": "ShapeAdventureFlow",
    "G5-AREA-MAT-14": "DirectionAdventureFlow",
    "G5-AREA-MAT-15": "DecimalAdventureFlow",
    "G5-AREA-MAT-16": "RomanAdventureFlow",
}


def orchestrator_with_learner(learner_id: UUID) -> tuple[LearningFlowOrchestrator, Session]:
    # Import every mapped model before creating the in-memory schema.  The production app imports
    # these during startup; this helper has to do the same explicitly.
    from app.gamification.infrastructure.db import models as _learning_flow_models  # noqa: F401

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=learner_id, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore

    return (
        LearningFlowOrchestrator(
            SqlAlchemyLearningFlowStore(session),
            probe_gateway=LocalProbeGateway(),
            evidence_publisher=RecordingEvidencePublisher(),
        ),
        session,
    )


def flow_for(orchestrator: LearningFlowOrchestrator, area_id: str):
    return orchestrator._area_flows[area_id]


def correct_answer(flow, record: Mapping[str, object]) -> dict[str, object]:
    return answers.correct_answer(flow, record)


def wrong_answer(flow, record: Mapping[str, object]) -> dict[str, object]:
    """The server's solution with one value changed, checked to score as wrong."""

    try:
        return answers.wrong_answer(flow, record)
    except ValueError as error:
        raise AssertionError(f"no wrong answer found for {record['skill_id']}") from error


def watch_demonstrations(
    orchestrator, episode_id: UUID, response: Mapping[str, object]
) -> Mapping[str, object]:
    """Press next through any watch-only visual demonstration, so an answerable round is open."""

    for step in range(8):
        status = response.get("support_round")
        support = response.get("support")
        if (
            not isinstance(status, Mapping)
            or not isinstance(support, Mapping)
            or status["stage_kind"] != "view"
            or support["scaffold_type"] != "visual_guidance"
        ):
            return response
        response = orchestrator.complete_support(
            episode_id,
            duration_ms=100,
            steps_viewed=1,
            manifest_revision_id=status["manifest_revision_id"],
            grouped_count=0,
            group_sizes=(0, 0),
            interaction_summary={"completed": True},
            idempotency_key=f"watch:{step}:{episode_id}",
        )
    return response


def finish_help(orchestrator, episode_id: UUID, shown: Mapping[str, object]) -> dict[str, str]:
    """Answer each help round correctly until the server allows withdrawal.

    Returns the ids the withdrawal acknowledgement must carry.
    """

    game_flow = orchestrator._adaptive_flow(episode_id)
    response = shown
    for step in range(16):
        status = response["support_round"]
        if status["withdrawal_allowed"]:
            return {
                "support_revision_id": status["support_revision_id"],
                "manifest_revision_id": status["manifest_revision_id"],
            }
        if status["stage_kind"] == "view":
            response = orchestrator.complete_support(
                episode_id,
                duration_ms=100,
                steps_viewed=1,
                manifest_revision_id=status["manifest_revision_id"],
                grouped_count=0,
                group_sizes=(0, 0),
                interaction_summary={"completed": True},
                idempotency_key=f"help-view:{step}:{episode_id}",
            )
            continue
        current = game_flow._support_rounds.current_item(
            orchestrator.reconstruct(episode_id)["state"]
        )
        response = orchestrator.submit_supported(
            episode_id,
            constructed_response=correct_answer(game_flow, current),
            response_time_ms=100,
            interaction_summary={},
            idempotency_key=f"help-answer:{step}:{episode_id}",
        )
    raise AssertionError("the help loop did not allow withdrawal")
