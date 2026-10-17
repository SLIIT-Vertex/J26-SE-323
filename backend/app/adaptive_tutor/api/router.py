from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.adaptive_tutor.api.contracts import TutorApiRequest, TutorApiResponse
from app.adaptive_tutor.application.orchestration import (
    TutorOrchestrator,
)
from app.adaptive_tutor.infrastructure.synthetic_orchestration import (
    UnknownSyntheticLearnerError,
    build_synthetic_tutor_orchestrator,
)
from app.config import Settings, get_settings

TutorOrchestratorFactory = Callable[[UUID], TutorOrchestrator]

router = APIRouter(prefix="/adaptive-tutor", tags=["adaptive-tutor"])


def get_tutor_orchestrator_factory() -> TutorOrchestratorFactory:
    return build_synthetic_tutor_orchestrator


@router.post(
    "/responses",
    response_model=TutorApiResponse,
    response_model_exclude_none=True,
    summary="Run the safely restricted Adaptive Tutor workflow",
    description=(
        "Runs only when TUTOR_API_MODE=synthetic-demo. Synthetic verification never "
        "authorizes delivery and generated drafts remain hidden."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Unknown controlled synthetic learner"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Malformed request"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Sanitized workflow failure"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Adaptive Tutor API disabled"},
    },
)
def create_tutor_response(
    request: Annotated[
        TutorApiRequest,
        Body(
            openapi_examples={
                "synthetic-l0": {
                    "summary": "Controlled synthetic L0 fixture",
                    "value": {
                        "learner_id": "00000000-0000-4000-8000-000000000001",
                        "student_message": "Help me understand this fractions problem.",
                        "response_language": "en",
                        "conversation_context": [],
                    },
                },
                "synthetic-ambiguous": {
                    "summary": "Controlled ambiguous mapping fixture",
                    "value": {
                        "learner_id": "00000000-0000-4000-8000-000000000001",
                        "student_message": "Can you help me?",
                        "response_language": "en",
                    },
                },
            }
        ),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    orchestrator_factory: Annotated[
        TutorOrchestratorFactory,
        Depends(get_tutor_orchestrator_factory),
    ],
) -> TutorApiResponse:
    if settings.tutor_api_mode == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive Tutor API is disabled.",
        )

    try:
        orchestrator = orchestrator_factory(request.learner_id)
    except UnknownSyntheticLearnerError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Synthetic learner fixture not found.",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive Tutor workflow could not be initialized safely.",
        ) from error

    try:
        result = orchestrator.run(request.to_workflow_request())
        return TutorApiResponse.from_workflow_result(result)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive Tutor workflow failed safely.",
        ) from error
