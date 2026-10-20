from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response, status

from app.adaptive_tutor.api.contracts import (
    DemoHistoryResponse,
    DemoInteractionResponse,
    DemoScenarioRead,
    ResearchAttemptRequest,
    ResearchAuthorizationResponse,
    ResearchInteractionResponse,
    ResearchQuestionRequest,
    StartDemoSessionRequest,
    StartDemoSessionResponse,
    StartResearchSessionRequest,
    StartResearchSessionResponse,
    SubmitDemoQuestionRequest,
    TutorApiRequest,
    TutorApiResponse,
)
from app.adaptive_tutor.application.orchestration import (
    SYNTHETIC_DEMO_NOTICE,
    TutorOrchestrator,
)
from app.adaptive_tutor.infrastructure.demo_sessions import (
    SCENARIOS,
    DemoSessionError,
    SyntheticDemoSessionStore,
    demo_access_allowed,
)
from app.adaptive_tutor.infrastructure.local_research import (
    build_local_research_tutor_service,
)
from app.adaptive_tutor.infrastructure.research_sessions import (
    ResearchSessionError,
    ResearchTutorService,
)
from app.adaptive_tutor.infrastructure.synthetic_orchestration import (
    UnknownSyntheticLearnerError,
    build_synthetic_tutor_orchestrator,
)
from app.config import Settings, get_settings
from app.shared.database.session import SessionLocal

TutorOrchestratorFactory = Callable[[UUID], TutorOrchestrator]

router = APIRouter(prefix="/adaptive-tutor", tags=["adaptive-tutor"])


def get_tutor_orchestrator_factory() -> TutorOrchestratorFactory:
    return build_synthetic_tutor_orchestrator


@lru_cache
def _demo_store(minutes: int) -> SyntheticDemoSessionStore:
    return SyntheticDemoSessionStore(lifetime=timedelta(minutes=minutes))


def get_demo_session_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyntheticDemoSessionStore:
    return _demo_store(settings.tutor_demo_session_minutes)


@lru_cache
def _local_research_service() -> ResearchTutorService:
    # ponytail: a single-process research service is enough until sessions become durable.
    return build_local_research_tutor_service(get_settings(), SessionLocal())


def get_research_tutor_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchTutorService | None:
    """Resolve the live composition only behind the explicit local opt-in."""

    if not settings.tutor_research_composition_enabled:
        return None
    try:
        return _local_research_service()
    except Exception:  # noqa: BLE001 - configuration/provider details stay server-side
        return None


def _require_demo_access(settings: Settings, supplied_key: str | None) -> None:
    if settings.tutor_api_mode == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive Tutor API is disabled.",
        )
    if settings.tutor_api_mode != "synthetic-demo":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive Tutor synthetic demo is disabled.",
        )
    if not demo_access_allowed(settings.tutor_demo_access_key, supplied_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Synthetic demo access denied.",
        )


def _session_token(value: str | None) -> str:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tutor session authorization required.",
        )
    return value


def _session_error(error: DemoSessionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Synthetic Tutor session not found or expired.",
    )


def _require_research_access(
    settings: Settings,
    supplied_key: str | None,
    client_host: str | None,
) -> UUID:
    if settings.tutor_api_mode != "research-local":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Research Tutor is disabled.")
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research Tutor is local-only.")
    if not demo_access_allowed(settings.tutor_research_access_key, supplied_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Researcher access denied.")
    try:
        return UUID(settings.tutor_researcher_id)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Researcher identity is not configured.",
        ) from error


def _research_session_error(error: ResearchSessionError) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        "Research Tutor session or interaction not found or expired.",
    )


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
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
) -> TutorApiResponse:
    _require_demo_access(settings, demo_access_key)

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


@router.get("/demo/scenarios", response_model=tuple[DemoScenarioRead, ...])
def list_demo_scenarios(
    settings: Annotated[Settings, Depends(get_settings)],
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
) -> tuple[DemoScenarioRead, ...]:
    _require_demo_access(settings, demo_access_key)
    return tuple(DemoScenarioRead.from_scenario(item) for item in SCENARIOS)


@router.post("/demo/sessions", response_model=StartDemoSessionResponse, status_code=201)
def start_demo_session(
    request: StartDemoSessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SyntheticDemoSessionStore, Depends(get_demo_session_store)],
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
) -> StartDemoSessionResponse:
    _require_demo_access(settings, demo_access_key)
    session, token = store.start(request.scenario_id)
    return StartDemoSessionResponse.from_session(session, token, SYNTHETIC_DEMO_NOTICE)


@router.post(
    "/demo/sessions/{session_id}/questions",
    response_model=DemoInteractionResponse,
    response_model_exclude_none=True,
)
def submit_demo_question(
    session_id: UUID,
    request: SubmitDemoQuestionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SyntheticDemoSessionStore, Depends(get_demo_session_store)],
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Session-Token")] = None,
) -> DemoInteractionResponse:
    _require_demo_access(settings, demo_access_key)
    token = _session_token(session_token)
    try:
        interaction = store.submit(
            session_id,
            token,
            student_message=request.student_message,
            response_language=request.response_language,
        )
        session = store.get(session_id, token)
    except DemoSessionError as error:
        raise _session_error(error) from error
    return DemoInteractionResponse.from_interaction(session, interaction)


@router.get(
    "/demo/sessions/{session_id}/history",
    response_model=DemoHistoryResponse,
    response_model_exclude_none=True,
)
def get_demo_history(
    session_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SyntheticDemoSessionStore, Depends(get_demo_session_store)],
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Session-Token")] = None,
) -> DemoHistoryResponse:
    _require_demo_access(settings, demo_access_key)
    token = _session_token(session_token)
    try:
        session = store.get(session_id, token)
        history = store.history(session_id, token)
    except DemoSessionError as error:
        raise _session_error(error) from error
    return DemoHistoryResponse(
        interactions=tuple(
            DemoInteractionResponse.from_interaction(session, item) for item in history
        )
    )


@router.delete("/demo/sessions/{session_id}", status_code=204)
def end_demo_session(
    session_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SyntheticDemoSessionStore, Depends(get_demo_session_store)],
    demo_access_key: Annotated[str | None, Header(alias="X-Tutor-Demo-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Session-Token")] = None,
) -> Response:
    _require_demo_access(settings, demo_access_key)
    try:
        store.end(session_id, _session_token(session_token))
    except DemoSessionError as error:
        raise _session_error(error) from error
    return Response(status_code=204)


@router.post("/research/sessions", response_model=StartResearchSessionResponse, status_code=201)
def start_research_session(
    request: StartResearchSessionRequest,
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[ResearchTutorService | None, Depends(get_research_tutor_service)],
    research_key: Annotated[str | None, Header(alias="X-Tutor-Research-Key")] = None,
) -> StartResearchSessionResponse:
    researcher_id = _require_research_access(settings, research_key, http_request.client.host)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Reviewed research provider composition is not configured.",
        )
    try:
        session, token = service.start(
            researcher_id=researcher_id,
            learner_id=request.learner_id,
        )
    except ResearchSessionError as error:
        raise _research_session_error(error) from error
    return StartResearchSessionResponse.from_session(session, token)


@router.get("/research/status", response_model=ResearchAuthorizationResponse)
def research_status(
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[ResearchTutorService | None, Depends(get_research_tutor_service)],
    research_key: Annotated[str | None, Header(alias="X-Tutor-Research-Key")] = None,
) -> ResearchAuthorizationResponse:
    _require_research_access(settings, research_key, http_request.client.host)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Reviewed research provider composition is not configured.",
        )
    return ResearchAuthorizationResponse()


@router.post(
    "/research/sessions/{session_id}/questions",
    response_model=ResearchInteractionResponse,
    response_model_exclude_none=True,
)
def ask_research_question(
    session_id: UUID,
    request: ResearchQuestionRequest,
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[ResearchTutorService | None, Depends(get_research_tutor_service)],
    research_key: Annotated[str | None, Header(alias="X-Tutor-Research-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Research-Session")] = None,
) -> ResearchInteractionResponse:
    _require_research_access(settings, research_key, http_request.client.host)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Research Tutor is unavailable.")
    try:
        turn = service.ask(
            session_id,
            _session_token(session_token),
            question=request.student_message,
            language=request.response_language,
        )
    except ResearchSessionError as error:
        raise _research_session_error(error) from error
    except PermissionError as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error)) from error
    except Exception as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Research Tutor dependencies are unavailable.",
        ) from error
    return ResearchInteractionResponse.from_turn(session_id, turn)


@router.post(
    "/research/sessions/{session_id}/interactions/{interaction_id}/attempts",
    response_model=ResearchInteractionResponse,
    response_model_exclude_none=True,
)
def submit_research_attempt(
    session_id: UUID,
    interaction_id: UUID,
    request: ResearchAttemptRequest,
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[ResearchTutorService | None, Depends(get_research_tutor_service)],
    research_key: Annotated[str | None, Header(alias="X-Tutor-Research-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Research-Session")] = None,
) -> ResearchInteractionResponse:
    _require_research_access(settings, research_key, http_request.client.host)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Research Tutor is unavailable.")
    try:
        turn = service.submit_attempt(
            session_id,
            _session_token(session_token),
            interaction_id,
            request.to_annotation(),
        )
    except ResearchSessionError as error:
        raise _research_session_error(error) from error
    except PermissionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except Exception as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Research assessment dependencies are unavailable.",
        ) from error
    return ResearchInteractionResponse.from_turn(session_id, turn)


@router.delete("/research/sessions/{session_id}", status_code=204)
def end_research_session(
    session_id: UUID,
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[ResearchTutorService | None, Depends(get_research_tutor_service)],
    research_key: Annotated[str | None, Header(alias="X-Tutor-Research-Key")] = None,
    session_token: Annotated[str | None, Header(alias="X-Tutor-Research-Session")] = None,
) -> Response:
    _require_research_access(settings, research_key, http_request.client.host)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Research Tutor is unavailable.")
    try:
        service.end(session_id, _session_token(session_token))
    except ResearchSessionError as error:
        raise _research_session_error(error) from error
    return Response(status_code=204)
