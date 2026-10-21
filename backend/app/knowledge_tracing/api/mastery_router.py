from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.knowledge_tracing.api.game_sync import sync_game_answers
from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
    MasteryService,
    ModelUnavailableError,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.domain.mastery import DEFINITION, MasterySnapshot
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.ml.service import (
    KnowledgeModel,
    get_knowledge_model,
)
from app.shared.database.session import get_db

router = APIRouter(prefix="/learners", tags=["mastery"])


class SkillMasteryRead(BaseModel):
    code: str
    area: str
    name_en: str
    name_si: str | None
    mastery: float | None  # None = not enough answers yet (fewer than 3)
    attempts: int


class MasteryRead(BaseModel):
    computed_at: datetime
    model_version: str
    n_attempts: int
    definition: str
    skills: list[SkillMasteryRead]


def get_estimator() -> KnowledgeModel:
    try:
        return get_knowledge_model()
    except (FileNotFoundError, OSError, RuntimeError) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The knowledge model is not available"
        ) from error


def get_mastery_service(
    session: Annotated[Session, Depends(get_db)],
    estimator: Annotated[KnowledgeModel, Depends(get_estimator)],
) -> MasteryService:
    return MasteryService(SqlAlchemyMasteryRepository(session), estimator, get_feature_spec())


def get_skill_catalog(
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, tuple[str, str, str | None]]:
    return SqlAlchemyMasteryRepository(session).skill_catalog()


def to_read(
    snapshot: MasterySnapshot, catalog: dict[str, tuple[str, str, str | None]]
) -> MasteryRead:
    skills = []
    for estimate in snapshot.skills:
        area, name_en, name_si = catalog.get(estimate.code, (estimate.code[:3], estimate.code, None))
        skills.append(
            SkillMasteryRead(
                code=estimate.code,
                area=area,
                name_en=name_en,
                name_si=name_si,
                mastery=estimate.mastery,
                attempts=estimate.attempts,
            )
        )
    return MasteryRead(
        computed_at=snapshot.computed_at,
        model_version=snapshot.model_version,
        n_attempts=snapshot.n_attempts,
        definition=DEFINITION,
        skills=skills,
    )


@router.get("/{learner_id}/mastery", response_model=MasteryRead, dependencies=[Depends(sync_game_answers)])
def get_mastery(
    learner_id: UUID,
    service: Annotated[MasteryService, Depends(get_mastery_service)],
    catalog: Annotated[dict[str, tuple[str, str, str | None]], Depends(get_skill_catalog)],
) -> MasteryRead:
    """The latest mastery for all 30 skills. `mastery` is null until a skill has 3 answers."""
    try:
        return to_read(service.current(learner_id), catalog)
    except LearnerNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found") from error
    except ModelUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The knowledge model is not available"
        ) from error


@router.post("/{learner_id}/mastery/recompute", response_model=MasteryRead)
def recompute_mastery(
    learner_id: UUID,
    service: Annotated[MasteryService, Depends(get_mastery_service)],
    catalog: Annotated[dict[str, tuple[str, str, str | None]], Depends(get_skill_catalog)],
) -> MasteryRead:
    """Force a recompute (admin/debug). Calls within a few seconds return the last result."""
    try:
        return to_read(service.recompute(learner_id), catalog)
    except LearnerNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found") from error
    except ModelUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The knowledge model is not available"
        ) from error
