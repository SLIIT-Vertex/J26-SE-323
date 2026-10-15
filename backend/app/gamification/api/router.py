"""Pilot episode HTTP surface. Development auth is NOT_FOR_PRODUCTION."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.gamification.api.dependencies import (
    NOT_FOR_PRODUCTION,
    build_authoring_desk,
    build_session_play,
)
from app.gamification.application.delivery import (
    METRICS,
    AuthoringDesk,
    RateLimiter,
    get_rate_limiter,
    request_fingerprint,
)
from app.gamification.application.errors import PlayError
from app.gamification.application.session_play import MAX_EVENTS, SessionPlay
from app.gamification.domain.types import DecisionMode

router = APIRouter(tags=["gamification-pilot"])
_play = build_session_play()
_desk = build_authoring_desk()


def get_play_service() -> SessionPlay:
    return _play


def get_authoring_desk() -> AuthoringDesk:
    return _desk


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
    language: str


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


class AssignmentRequest(Boundary):
    experiment_id: UUID
    learner_id: UUID
    seed: int = Field(ge=0, le=2_147_483_647)
    protocol_hash: str = Field(min_length=64, max_length=64)


class AssignmentView(Boundary):
    experiment_id: UUID
    learner_id: UUID
    arm_key: str
    decision_mode: str
    seed: int


class MonitoringView(Boundary):
    episodes: int
    invalid_episode_rate_by_reason: dict[str, float]
    invalid_episodes: int
    fallback_rate: float
    action_coverage_by_arm: dict[str, dict[str, int]]
    verification_availability: float
    abstention_rate: float
    inputs: str


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


class LearnerStepView(Boundary):
    episode_id: UUID
    next_step: Literal[
        "continue", "present_support", "present_verification", "finish", "safe_fallback"
    ]
    template_key: str | None


class SessionSummary(Boundary):
    session_id: UUID
    status: str


class GameProgressView(Boundary):
    learner_id: UUID
    session_count: int
    sessions: tuple[SessionSummary, ...]
    next_cursor: str | None


class SkillProgressView(Boundary):
    learner_id: UUID
    skill_code: str
    unsupported_attempts: int
    supported_exposures: int
    independent_accuracy: float | None
    supported_accuracy: float | None
    mean_independence_gain: float | None


class RewardEntryView(Boundary):
    episode_id: UUID
    points: int
    reason_code: str


class RewardsView(Boundary):
    learner_id: UUID
    balance: int
    entries: tuple[RewardEntryView, ...]


class ManifestOption(Boundary):
    option_id: str
    text: str


class InstanceManifestView(Boundary):
    instance_id: str
    language: str
    skill_code: str
    prompt_label: str
    options: tuple[ManifestOption, ...]
    content_version: int


class SourceRequest(Boundary):
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    grade: Literal[5]
    language: Literal["si"]
    version: str = Field(min_length=1, max_length=64)


class IngestRequest(Boundary):
    text: str = Field(min_length=1, max_length=4_000)


class SkillMappingRequest(Boundary):
    skill_code: str = Field(min_length=1, max_length=128)
    universal_skill_id: str = Field(min_length=1, max_length=16)
    source_id: str = Field(min_length=1, max_length=128)
    mapping_version: str = Field(min_length=1, max_length=64)


class GameInstanceRequest(Boundary):
    instance_id: str = Field(min_length=1, max_length=128)
    skill_code: str = Field(min_length=1, max_length=128)
    language: Literal["si"]
    prompt_label: str = Field(min_length=1, max_length=200)
    option_labels: tuple[str, ...] = Field(min_length=2, max_length=6)


class SupportAssetRequest(Boundary):
    asset_id: str = Field(min_length=1, max_length=128)
    scaffold_type: str = Field(min_length=1, max_length=64)
    step_count: int = Field(ge=1, le=20)


class VerificationPairRequest(Boundary):
    pair_id: str = Field(min_length=1, max_length=128)
    baseline_instance_id: str = Field(min_length=1, max_length=128)
    verification_instance_id: str = Field(min_length=1, max_length=128)


class ContentApprovalRequest(Boundary):
    reviewer_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approve", "revoke"] = "approve"


class ModelApprovalRequest(Boundary):
    model_version: str = Field(min_length=1, max_length=128)
    artifact_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision: Literal["approve", "revoke"] = "approve"


class ConsentReferenceRequest(Boundary):
    learner_id: UUID
    purpose: Literal["research_export"]
    consent_reference: str = Field(min_length=1, max_length=128)
    consent_version: str = Field(min_length=1, max_length=64)


class ExportRequest(Boundary):
    learner_id: UUID
    purpose: Literal["research_export"]


class AcceptedView(Boundary):
    status: str


class JobView(Boundary):
    source_id: str | None = None
    job_id: UUID | None = None
    status: str
    content_id: str | None = None
    instance_id: str | None = None
    asset_id: str | None = None
    pair_id: str | None = None
    version: str | int | None = None


class ApprovalView(Boundary):
    content_id: str | None = None
    model_id: str | None = None
    status: str | None = None
    version: int | None = None
    approved: bool | None = None
    model_version: str | None = None


class ExportView(Boundary):
    export_id: UUID
    learner_id: UUID
    purpose: str
    consent_reference: str
    status: str
    records: dict[str, str | bool]


class MetricsView(Boundary):
    requests: int
    errors: int
    latency_p95_ms: float
    event_accepted: int
    event_duplicates: int
    event_quarantined: int
    fallbacks: int
    abstentions: int
    support_failures: int
    verification_unavailable: int
    job_failures: int
    spans: tuple[str, ...]


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
    if x_dev_principal != NOT_FOR_PRODUCTION or x_dev_role not in {
        "learner",
        "researcher",
        "admin",
    }:
        raise PlayError("DEV_AUTH_REQUIRED", 401)
    if x_dev_role == "learner" and x_learner_id is None:
        raise PlayError("DEV_AUTH_REQUIRED", 401)
    return x_dev_role, x_learner_id


def _learner(principal: Annotated[tuple[str, UUID | None], Depends(_principal)]) -> UUID:
    role, learner_id = principal
    if role != "learner" or learner_id is None:
        raise PlayError("LEARNER_ACCESS_DENIED", 403)
    return learner_id


def _limited(
    learner_id: Annotated[UUID, Depends(_learner)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UUID:
    limiter.allow(str(learner_id), datetime.now(UTC))
    return learner_id


def _admin(principal: Annotated[tuple[str, UUID | None], Depends(_principal)]) -> None:
    if principal[0] != "admin":
        raise PlayError("ADMIN_ROLE_REQUIRED", 403)


def _researcher(principal: Annotated[tuple[str, UUID | None], Depends(_principal)]) -> None:
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


_SESSION_EXAMPLE = {
    "session_id": "00000000-0000-4000-8000-000000000301",
    "learner_id": "00000000-0000-4000-8000-000000000201",
    "status": "active",
    "language": "si",
}


@router.post(
    "/game-sessions",
    responses={200: {"content": {"application/json": {"example": _SESSION_EXAMPLE}}}},
)
def create_session(
    body: CreateSessionRequest,
    response: Response,
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SessionCreated:
    _same_learner(body.learner_id, learner_id)
    if body.language != "si":
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
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SessionCreated:
    result = play.complete_session(session_id, learner_id=learner_id, idempotency_key=key)
    return _typed(SessionCreated, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/next-activity")
def next_activity(
    session_id: UUID,
    body: NextActivityRequest,
    response: Response,
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    mode: Annotated[DecisionMode, Depends(_mode)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
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
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
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
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
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
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> StepView:
    result = play.withdraw_support(episode_id, learner_id=learner_id, idempotency_key=key)
    return _typed(StepView, result, response, correlation_id)


@router.post(
    "/game-sessions/{session_id}/events:batch",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "accepted": 1,
                        "duplicate": 0,
                        "quarantined": 0,
                        "expected_next_sequence": 2,
                    }
                }
            }
        }
    },
)
def ingest_events(
    session_id: UUID,
    body: EventBatchRequest,
    response: Response,
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
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


@router.post("/experiments/assignments")
def assign_experiment_arm(
    body: AssignmentRequest,
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> AssignmentView:
    result = play.assign_arm(
        experiment_id=body.experiment_id,
        learner_id=body.learner_id,
        seed=body.seed,
        protocol_hash=body.protocol_hash,
        idempotency_key=key,
    )
    return _typed(AssignmentView, result, response, correlation_id)


@router.get("/evaluation/monitoring")
def evaluation_monitoring(
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> MonitoringView:
    return _typed(MonitoringView, play.monitoring(), response, correlation_id)


@router.get("/adaptive-episodes/{episode_id}/reconstruction")
def reconstruct(
    episode_id: UUID,
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> ReconstructionView:
    return _typed(ReconstructionView, play.reconstruct(episode_id), response, correlation_id)


@router.get("/game-sessions/{session_id}")
def read_session(
    session_id: UUID,
    response: Response,
    learner_id: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SessionCreated:
    return _typed(
        SessionCreated,
        play.get_session(session_id, learner_id=learner_id),
        response,
        correlation_id,
    )


@router.post("/game-sessions/{session_id}/pause")
def pause_session(
    session_id: UUID,
    response: Response,
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SessionCreated:
    result = play.pause_session(session_id, learner_id=learner_id, idempotency_key=key)
    return _typed(SessionCreated, result, response, correlation_id)


@router.post("/game-sessions/{session_id}/resume")
def resume_session(
    session_id: UUID,
    response: Response,
    learner_id: Annotated[UUID, Depends(_limited)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SessionCreated:
    result = play.resume_session(session_id, learner_id=learner_id, idempotency_key=key)
    return _typed(SessionCreated, result, response, correlation_id)


@router.get("/adaptive-episodes/{episode_id}/next-step")
def learner_next_step(
    episode_id: UUID,
    response: Response,
    learner_id: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> LearnerStepView:
    return _typed(
        LearnerStepView,
        play.learner_next_step(episode_id, learner_id=learner_id),
        response,
        correlation_id,
    )


@router.get("/learners/{learner_id}/game-progress")
def game_progress(
    learner_id: UUID,
    response: Response,
    token_learner: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> GameProgressView:
    _same_learner(learner_id, token_learner)
    return _typed(
        GameProgressView,
        play.game_progress(learner_id, cursor=cursor, limit=limit),
        response,
        correlation_id,
    )


@router.get("/learners/{learner_id}/skill-progress/{skill_code}")
def skill_progress(
    learner_id: UUID,
    skill_code: str,
    response: Response,
    token_learner: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> SkillProgressView:
    _same_learner(learner_id, token_learner)
    return _typed(
        SkillProgressView,
        play.skill_progress(learner_id, skill_code),
        response,
        correlation_id,
    )


@router.get("/learners/{learner_id}/rewards")
def learner_rewards(
    learner_id: UUID,
    response: Response,
    token_learner: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    play: Annotated[SessionPlay, Depends(get_play_service)],
) -> RewardsView:
    _same_learner(learner_id, token_learner)
    return _typed(RewardsView, play.rewards(learner_id), response, correlation_id)


@router.get("/game-instances/{instance_id}/manifest")
def instance_manifest(
    instance_id: str,
    response: Response,
    _learner_id: Annotated[UUID, Depends(_learner)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> InstanceManifestView:
    return _typed(InstanceManifestView, desk.manifest(instance_id), response, correlation_id)


def _admin_once(
    desk: AuthoringDesk, key: str, payload: dict[str, object], produce
) -> dict[str, object]:
    return desk.once(key, request_fingerprint(payload), produce)


@router.post("/admin/curriculum-sources")
def register_source(
    body: SourceRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    payload = body.model_dump(mode="json")
    result = _admin_once(desk, key, payload, lambda: desk.register_source(**payload))
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/curriculum-sources/{source_id}/ingest")
def ingest_source(
    source_id: str,
    body: IngestRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    result = _admin_once(
        desk,
        key,
        {"source_id": source_id, "text": body.text},
        lambda: desk.ingest(source_id, text=body.text, idempotency_key=key),
    )
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/skill-mappings")
def map_skill(
    body: SkillMappingRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    payload = body.model_dump(mode="json")
    result = _admin_once(desk, key, payload, lambda: desk.map_skill(**payload))
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/game-instances")
def create_instance(
    body: GameInstanceRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    payload = body.model_dump(mode="json")
    result = _admin_once(
        desk,
        key,
        payload,
        lambda: desk.create_instance(
            instance_id=body.instance_id,
            skill_code=body.skill_code,
            language=body.language,
            prompt_label=body.prompt_label,
            option_labels=body.option_labels,
        ),
    )
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/support-assets")
def create_support_asset(
    body: SupportAssetRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    payload = body.model_dump(mode="json")
    result = _admin_once(
        desk,
        key,
        payload,
        lambda: desk.create_support_asset(
            asset_id=body.asset_id, scaffold_type=body.scaffold_type, step_count=body.step_count
        ),
    )
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/verification-pairs")
def create_pair(
    body: VerificationPairRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> JobView:
    payload = body.model_dump(mode="json")
    result = _admin_once(
        desk,
        key,
        payload,
        lambda: desk.create_verification_pair(
            pair_id=body.pair_id,
            baseline_instance_id=body.baseline_instance_id,
            verification_instance_id=body.verification_instance_id,
        ),
    )
    return _typed(JobView, result, response, correlation_id)


@router.post("/admin/content/{content_id}/approve")
def approve_content(
    content_id: str,
    body: ContentApprovalRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> ApprovalView:
    result = _admin_once(
        desk,
        key,
        {"content_id": content_id, **body.model_dump(mode="json")},
        lambda: desk.approve_content(
            content_id, reviewer_id=body.reviewer_id, decision=body.decision
        ),
    )
    return _typed(ApprovalView, result, response, correlation_id)


@router.post("/admin/model-versions/{model_id}/approve")
def approve_model(
    model_id: str,
    body: ModelApprovalRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> ApprovalView:
    result = _admin_once(
        desk,
        key,
        {"model_id": model_id, **body.model_dump(mode="json")},
        lambda: desk.approve_model(
            model_id,
            model_version=body.model_version,
            artifact_digest=body.artifact_digest,
            decision=body.decision,
        ),
    )
    return _typed(ApprovalView, result, response, correlation_id)


@router.post("/admin/consent-references")
def note_consent(
    body: ConsentReferenceRequest,
    response: Response,
    _role: Annotated[None, Depends(_admin)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> AcceptedView:
    payload = body.model_dump(mode="json")
    _admin_once(
        desk,
        key,
        payload,
        lambda: desk.note_consent_reference(
            learner_id=body.learner_id,
            purpose=body.purpose,
            reference=body.consent_reference,
            consent_version=body.consent_version,
        ),
    )
    return _typed(AcceptedView, {"status": "recorded"}, response, correlation_id)


@router.post("/research/exports")
def create_export(
    body: ExportRequest,
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    key: Annotated[str, Depends(_key)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> ExportView:
    result = _admin_once(
        desk,
        key,
        body.model_dump(mode="json"),
        lambda: desk.create_export(learner_id=body.learner_id, purpose=body.purpose),
    )
    return _typed(ExportView, result, response, correlation_id)


@router.get("/research/exports/{export_id}")
def read_export(
    export_id: UUID,
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    correlation_id: Annotated[str, Depends(_correlation)],
    desk: Annotated[AuthoringDesk, Depends(get_authoring_desk)],
) -> ExportView:
    return _typed(ExportView, desk.get_export(export_id), response, correlation_id)


@router.get("/evaluation/delivery-metrics")
def delivery_metrics(
    response: Response,
    _role: Annotated[None, Depends(_researcher)],
    correlation_id: Annotated[str, Depends(_correlation)],
) -> MetricsView:
    return _typed(MetricsView, METRICS.snapshot(), response, correlation_id)


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
