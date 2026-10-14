"""Pilot episode HTTP surface. Development auth is NOT_FOR_PRODUCTION."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION, build_session_play
from app.gamification.application.errors import PlayError
from app.gamification.application.session_play import MAX_EVENTS, SessionPlay
from app.gamification.domain.types import DecisionMode

router = APIRouter(tags=["gamification-pilot"])
_play = build_session_play()


def get_play_service() -> SessionPlay:
    return _play


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionRequest(Boundary):
    learner_id: UUID
    client_session_id: UUID
    language: str = Field(default="si", min_length=2, max_length=8)


class NextActivityRequest(Boundary):
    skill_id: str = Field(min_length=1, max_length=128)
    device_capabilities: tuple[str, ...] = Field(
        default=("choice_quest", "build_manipulate"), min_length=1, max_length=8
    )


class ResponseRequest(Boundary):
    episode_id: UUID
    selected_option_id: str = Field(min_length=1, max_length=32)
    response_time_ms: int | None = Field(default=None, ge=0, le=86_400_000)


class SupportCompleteRequest(Boundary):
    duration_ms: int = Field(ge=0, le=86_400_000)
    step_count: int = Field(ge=0, le=100)


class TelemetryEvent(Boundary):
    event_id: UUID
    sequence_no: int = Field(ge=1, le=1_000_000)
    event_type: Literal[
        "item_presented",
        "option_selected",
        "option_changed",
        "answer_submitted",
        "support_presented",
        "support_dismissed",
        "support_withdrawn",
        "verification_presented",
        "verification_submitted",
    ]
    event_version: Literal[1]
    client_occurred_at: str = Field(min_length=1, max_length=40)
    payload: dict[str, str | int | bool] = Field(default_factory=dict, max_length=8)


class EventBatchRequest(Boundary):
    first_sequence_no: int = Field(ge=1, le=1_000_000)
    events: tuple[TelemetryEvent, ...] = Field(min_length=1, max_length=MAX_EVENTS)


class SessionCreated(Boundary):
    session_id: UUID
    learner_id: UUID
    status: str


class OptionView(Boundary):
    option_id: str
    text: str


class ManifestView(Boundary):
    item_id: str
    question_text: str
    language: str
    template_key: str
    options: tuple[OptionView, ...]


class SupportView(Boundary):
    scaffold_type: str
    title: str
    steps: tuple[str, ...]
    maximum_duration_ms: int
    maximum_number_of_steps: int
    diagram: dict[str, str | int | float | bool] | None = None


class StepView(Boundary):
    episode_id: UUID
    template_key: str | None
    next_step: Literal[
        "continue", "present_support", "present_verification", "finish", "safe_fallback"
    ]
    manifest: ManifestView | None
    support: SupportView | None


class SupportContinued(Boundary):
    episode_id: UUID
    next_step: Literal["continue"]


class EventBatchResult(Boundary):
    accepted: int
    duplicate: int
    quarantined: int
    expected_next_sequence: int


class BeliefView(Boundary):
    code: str
    probability: float


class CandidateView(Boundary):
    action_id: str
    action_type: str
    propensity: float
    predicted_reward: float | None
    eligible: bool


class ReconstructionView(Boundary):
    episode_id: UUID
    phase: str
    beliefs: tuple[BeliefView, ...]
    candidates: tuple[CandidateView, ...]
    delivered_scaffold_id: str | None
    baseline_score: float | None
    verification_score: float | None
    independence_gain: float | None
    validity: str | None


def _correlation(request: Request) -> str:
    supplied = request.headers.get("x-correlation-id")
    if supplied is not None and len(supplied) > 64:
        raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
    value = supplied or str(uuid4())
    request.state.correlation_id = value
    return value


def _principal(
    x_dev_principal: Annotated[str | None, Header(alias="X-Dev-Principal")] = None,
    x_dev_role: Annotated[str | None, Header(alias="X-Dev-Role")] = None,
    x_learner_id: Annotated[UUID | None, Header(alias="X-Learner-Id")] = None,
) -> tuple[str, UUID | None]:
    if x_dev_principal != NOT_FOR_PRODUCTION or x_dev_role not in {"learner", "researcher"}:
        raise PlayError("DEV_AUTH_REQUIRED", 401)
    if x_dev_role == "learner" and x_learner_id is None:
        raise PlayError("DEV_AUTH_REQUIRED", 401)
    return x_dev_role, x_learner_id


def _learner(principal: tuple[str, UUID | None] = Depends(_principal)) -> UUID:
    role, learner_id = principal
    if role != "learner" or learner_id is None:
        raise PlayError("LEARNER_ACCESS_DENIED", 403)
    return learner_id


def _researcher(principal: tuple[str, UUID | None] = Depends(_principal)) -> None:
    if principal[0] != "researcher":
        raise PlayError("RESEARCHER_ROLE_REQUIRED", 403)


def _key(idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str:
    if idempotency_key is None or not idempotency_key.strip():
        raise PlayError("IDEMPOTENCY_KEY_REQUIRED", 400)
    return idempotency_key


def _mode(x_decision_mode: Annotated[str | None, Header()] = None) -> DecisionMode:
    if x_decision_mode is None:
        return DecisionMode.PERFORMANCE_TRIGGERED_FIXED
    try:
        return DecisionMode(x_decision_mode)
    except ValueError as error:
        raise PlayError("MODEL_NOT_READY", 409) from error


def _same_learner(body_learner: UUID, token_learner: UUID) -> None:
    if body_learner != token_learner:
        raise PlayError("LEARNER_ACCESS_DENIED", 403)


@router.post("/game-sessions")
def create_session(
    body: CreateSessionRequest,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> SessionCreated:
    _same_learner(body.learner_id, learner_id)
    if body.language not in {"si", "ta", "en"}:
        raise PlayError("LANGUAGE_NOT_AVAILABLE", 409)
    result = play.create_session(
        learner_id=body.learner_id,
        client_session_id=body.client_session_id,
        language=body.language,
        idempotency_key=key,
    )
    return _typed(SessionCreated, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/complete")
def complete_session(
    session_id: UUID,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> SessionCreated:
    result = play.complete_session(session_id, learner_id=learner_id, idempotency_key=key)
    return _typed(SessionCreated, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/next-activity")
def next_activity(
    session_id: UUID,
    body: NextActivityRequest,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    mode: DecisionMode = Depends(_mode),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> StepView:
    result = play.next_activity(
        session_id,
        learner_id=learner_id,
        skill_id=body.skill_id,
        device_capabilities=body.device_capabilities,
        decision_mode=mode,
        idempotency_key=key,
    )
    return _typed(StepView, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/responses")
def submit_response(
    session_id: UUID,
    body: ResponseRequest,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> StepView:
    result = play.submit_response(
        session_id,
        learner_id=learner_id,
        episode_id=body.episode_id,
        selected_option_id=body.selected_option_id,
        response_time_ms=body.response_time_ms,
        idempotency_key=key,
    )
    return _typed(StepView, result, response, correlation_id)


@router.post("/adaptive-episodes/{episode_id}/support/complete")
def complete_support(
    episode_id: UUID,
    body: SupportCompleteRequest,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> SupportContinued:
    result = play.complete_support(
        episode_id,
        learner_id=learner_id,
        duration_ms=body.duration_ms,
        step_count=body.step_count,
        idempotency_key=key,
    )
    return _typed(SupportContinued, result, response, correlation_id)


@router.post("/adaptive-episodes/{episode_id}/support/withdraw")
def withdraw_support(
    episode_id: UUID,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> StepView:
    result = play.withdraw_support(episode_id, learner_id=learner_id, idempotency_key=key)
    return _typed(StepView, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/events:batch")
def ingest_events(
    session_id: UUID,
    body: EventBatchRequest,
    response: Response,
    learner_id: UUID = Depends(_learner),
    key: str = Depends(_key),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> EventBatchResult:
    events = tuple(event.model_dump(mode="json") for event in body.events)
    result = play.ingest_events(
        session_id,
        learner_id=learner_id,
        first_sequence_no=body.first_sequence_no,
        events=events,
        idempotency_key=key,
    )
    return _typed(EventBatchResult, result, response, correlation_id)


@router.get("/adaptive-episodes/{episode_id}/reconstruction")
def reconstruct(
    episode_id: UUID,
    response: Response,
    _role: None = Depends(_researcher),
    correlation_id: str = Depends(_correlation),
    play: SessionPlay = Depends(get_play_service),
) -> ReconstructionView:
    return _typed(ReconstructionView, play.reconstruct(episode_id), response, correlation_id)


def play_error_response(request: Request, error: PlayError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get(
        "x-correlation-id"
    )
    if not correlation_id or len(str(correlation_id)) > 64:
        correlation_id = str(uuid4())
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "correlation_id": correlation_id},
        headers={"X-Correlation-ID": str(correlation_id)},
    )


def _typed[Model: Boundary](
    model: type[Model], body: dict[str, object], response: Response, correlation_id: str
) -> Model:
    response.headers["X-Correlation-ID"] = correlation_id
    return model.model_validate(body)


def register_play_errors(app: object) -> None:
    app.add_exception_handler(PlayError, play_error_response)  # type: ignore[attr-defined]
