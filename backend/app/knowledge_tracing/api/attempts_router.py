from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.knowledge_tracing.api.schemas import AttemptCreate, AttemptCreated
from app.knowledge_tracing.application.attempts import (
    AnsweredInFutureError,
    AttemptService,
    DigitalAttemptCommand,
    IdempotencyKeyReusedError,
    InvalidAttemptError,
    LanguageNotAvailableError,
    LearnerNotFoundError,
    QuestionNotFoundError,
    SkillNotFoundError,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.shared.database.session import get_db

router = APIRouter(prefix="/attempts", tags=["attempts"])


def get_attempt_service(session: Annotated[Session, Depends(get_db)]) -> AttemptService:
    return AttemptService(SqlAlchemyAttemptRepository(session), get_feature_spec())


@router.post("", response_model=AttemptCreated, status_code=status.HTTP_201_CREATED)
def log_attempt(
    body: AttemptCreate,
    response: Response,
    service: Annotated[AttemptService, Depends(get_attempt_service)],
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
) -> AttemptCreated:
    """Log one digital (game) answer. A repeated Idempotency-Key returns the same attempt.

    The answer is either for a question of the paper question bank (`question_id`), or, for the
    game's own questions, carries its `skill_code` (one of the 30) and its `difficulty`.
    """
    command = DigitalAttemptCommand(
        learner_id=body.learner_id,
        question_id=body.question_id,
        skill_code=body.skill_code,
        difficulty=body.difficulty,
        language=body.language,
        correct=body.correct,
        answered_at=body.answered_at,
        time_ms=body.time_ms,
        hints=body.hints,
        idempotency_key=idempotency_key or None,
    )
    try:
        attempt, created = service.log_digital_attempt(command)
    except LearnerNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found") from error
    except QuestionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found") from error
    except SkillNotFoundError as error:
        raise HTTPException(422, "Unknown skill_code") from error
    except InvalidAttemptError as error:
        raise HTTPException(422, str(error)) from error
    except LanguageNotAvailableError as error:
        raise HTTPException(
            422, "Question is not available in that language"
        ) from error
    except AnsweredInFutureError as error:
        raise HTTPException(
            422, "answered_at is in the future"
        ) from error
    except IdempotencyKeyReusedError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Idempotency-Key was already used for a different answer"
        ) from error

    if not created:
        response.status_code = status.HTTP_200_OK
    assert attempt.id is not None
    return AttemptCreated(attempt_id=attempt.id)
