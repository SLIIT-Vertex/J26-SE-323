"""Read-only research dashboard routes. Development researcher principal only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.gamification.api.learning_flow_router import _researcher
from app.gamification.application.research_dashboard.dashboard import ResearchDashboardService
from app.gamification.infrastructure.db.research_dashboard_reader import (
    SqlAlchemyResearchDashboardReader,
)
from app.shared.database.session import get_db


def _enabled() -> None:
    if not get_settings().research_dashboard_enabled:
        raise HTTPException(status_code=404)


router = APIRouter(
    prefix="/research-dashboard",
    tags=["research-dashboard"],
    dependencies=[Depends(_enabled), Depends(_researcher)],
)


def _service(db: Annotated[Session, Depends(get_db)]) -> ResearchDashboardService:
    return ResearchDashboardService(SqlAlchemyResearchDashboardReader(db))


Service = Annotated[ResearchDashboardService, Depends(_service)]


@router.get("/learners/{learner}/overview")
def overview(
    learner: UUID,
    service: Service,
    include_invalidated: bool = False,
) -> dict[str, object]:
    return service.overview(learner, include_invalidated=include_invalidated)


@router.get("/learners/{learner}/episodes")
def episodes(
    learner: UUID,
    service: Service,
    skill_id: str | None = None,
    source: str | None = Query(default=None, pattern="^(seeded|live)$"),
    include_invalidated: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return service.episodes(
        learner,
        skill_id=skill_id,
        source=source,
        include_invalidated=include_invalidated,
        limit=limit,
        offset=offset,
    )


@router.get("/episodes/{episode_id}/trace")
def trace(episode_id: UUID, service: Service) -> dict[str, object]:
    result = service.trace(episode_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "EPISODE_NOT_FOUND"})
    return result


@router.get("/learners/{learner}/live")
def live(learner: UUID, service: Service) -> dict[str, object]:
    return service.live(learner)


@router.get("/learners/{learner}/learner-state")
def learner_state(learner: UUID, service: Service) -> dict[str, object]:
    return service.learner_state(learner)


@router.get("/learners/{learner}/model-history/{model}")
def history(
    learner: UUID,
    model: Annotated[str, Path(pattern="^(misconception|support|gain)$")],
    service: Service,
) -> dict[str, object]:
    return service.model_history(learner, model)


@router.get("/learners/{learner}/model-series/{model}")
def series(
    learner: UUID,
    model: Annotated[str, Path(pattern="^(misconception|support|gain)$")],
    service: Service,
) -> dict[str, object]:
    return service.model_series(learner, model)


@router.get("/learners/{learner}/profile")
def profile(learner: UUID, service: Service) -> dict[str, object]:
    return service.profile(learner)


@router.get("/learners/{learner}/accuracy")
def accuracy(learner: UUID, service: Service) -> dict[str, object]:
    return service.accuracy(learner)
