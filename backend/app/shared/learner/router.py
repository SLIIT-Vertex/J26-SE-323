from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.shared.database.session import get_db
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from app.shared.learner.schemas import LearnerCreate, LearnerRead
from app.shared.learner.service import LearnerNotFoundError, LearnerService

router = APIRouter(prefix="/learners", tags=["learners"])


def get_service(session: Annotated[Session, Depends(get_db)]) -> LearnerService:
    return LearnerService(SqlAlchemyLearnerRepository(session))


@router.post("", response_model=LearnerRead, status_code=status.HTTP_201_CREATED)
def create_learner(
    learner: LearnerCreate, service: Annotated[LearnerService, Depends(get_service)]
) -> LearnerRead:
    return LearnerRead.model_validate(service.create(learner.grade, learner.preferred_language))


@router.get("", response_model=list[LearnerRead])
def list_learners(service: Annotated[LearnerService, Depends(get_service)]) -> list[LearnerRead]:
    return [LearnerRead.model_validate(learner) for learner in service.list()]


@router.get("/{learner_id}", response_model=LearnerRead)
def get_learner(
    learner_id: UUID, service: Annotated[LearnerService, Depends(get_service)]
) -> LearnerRead:
    try:
        return LearnerRead.model_validate(service.get(learner_id))
    except LearnerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found") from error

