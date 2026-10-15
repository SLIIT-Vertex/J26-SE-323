"""Development-only HTTP adapter for the durable episode coordinator."""

# FastAPI dependency injection intentionally uses Depends calls in defaults.
# ruff: noqa: B008

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION
from app.gamification.application.delivery import RateLimiter, get_rate_limiter
from app.gamification.application.phase6_orchestration import (
    Phase6OrchestrationError,
    Phase6Orchestrator,
)
from app.gamification.infrastructure.db.phase6_gateways import (
    SqlAlchemyPhase6EvidencePublisher,
    SqlAlchemyProbeGateway,
)
from app.gamification.infrastructure.db.phase6_orchestration_store import (
    SqlAlchemyPhase6Store,
)
from app.shared.database.session import get_db
from app.shared.learner.repository import SqlAlchemyLearnerRepository

router = APIRouter(prefix="/development/phase6", tags=["gamification-phase6-development"])


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenEpisodeRequest(Boundary):
    learner_id: UUID
    session_id: UUID
    grade: Literal[5]
    medium: Literal["si"]
    condition: Literal["baseline", "proposed"]
    environment: Literal["development", "test"]
    allow_draft: Literal[True]


class AnswerRequest(Boundary):
    option_id: str = Field(min_length=1, max_length=32)


class SupportCompleteRequest(Boundary):
    duration_ms: int = Field(ge=0, le=86_400_000)
    steps_viewed: int = Field(ge=1, le=8)


class TelemetryEvent(Boundary):
    event_id: UUID
    sequence: int = Field(ge=1, le=1_000_000)
    version: Literal[1]
    payload: dict[str, str | int | bool] = Field(default_factory=dict, max_length=8)


class TelemetryBatch(Boundary):
    batch_id: UUID
    first_sequence: int = Field(ge=1, le=1_000_000)
    events: tuple[TelemetryEvent, ...] = Field(min_length=1, max_length=50)


class PublicOption(Boundary):
    option_id: str
    text_si: str


class PresentationManifest(Boundary):
    presentation_id: UUID
    revision_id: str
    measurement_role: Literal[
        "practice", "unsupported_before", "supported_practice", "unsupported_after", "retention"
    ]
    assistance_state: Literal["none", "active", "adult", "tutor", "unknown"]
    prompt_si: str
    accessibility_label_si: str
    options: tuple[PublicOption, ...]
    content_version: str


class HalfSetGameManifest(Boundary):
    schema_version: Literal["half-set-manifest-v1"]
    activity_id: str
    revision_id: str
    deterministic_seed: int
    total_objects: int = Field(ge=2, le=40)
    group_count: Literal[2]
    object_label_si: str
    instruction_si: str


class SupportView(Boundary):
    scaffold_id: str
    revision_id: str
    scaffold_type: Literal[
        "visual_guidance", "worked_parallel_example", "step_by_step_guidance"
    ]
    title_si: str
    body_si: tuple[str, ...]
    visual_alt_text_si: str | None
    maximum_steps: int
    game_manifest: HalfSetGameManifest


class ParticipationReward(Boundary):
    points: int
    reason: str


class ChildEpisodeResponse(Boundary):
    model_config = ConfigDict(extra="ignore")

    episode_id: UUID
    status: str
    manifest: PresentationManifest | None = None
    support: SupportView | None = None
    reward: ParticipationReward | None = None


class TelemetryAcknowledgement(Boundary):
    accepted: int
    duplicates: int
    next_sequence: int


def get_phase6_orchestrator(db: Session = Depends(get_db)) -> Phase6Orchestrator:
    return Phase6Orchestrator(
        SqlAlchemyPhase6Store(db),
        probe_gateway=SqlAlchemyProbeGateway(db),
        evidence_publisher=SqlAlchemyPhase6EvidencePublisher(db),
    )


def _key(value: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str:
    if value is None or not value.strip() or len(value) > 128:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    return value


def _principal(
    marker: Annotated[str | None, Header(alias="X-Dev-Principal")] = None,
    role: Annotated[str | None, Header(alias="X-Dev-Role")] = None,
    learner_id: Annotated[UUID | None, Header(alias="X-Learner-Id")] = None,
) -> tuple[str, UUID | None]:
    if marker != NOT_FOR_PRODUCTION or role not in {"learner", "researcher"}:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED"})
    if role == "learner" and learner_id is None:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED"})
    return role, learner_id


def _learner(
    principal: tuple[str, UUID | None] = Depends(_principal),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> UUID:
    if principal[0] != "learner" or principal[1] is None:
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN"})
    limiter.allow(f"phase6:{principal[1]}", datetime.now(UTC))
    return principal[1]


def _researcher(principal: tuple[str, UUID | None] = Depends(_principal)) -> None:
    if principal[0] != "researcher":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN"})


def _call(operation):
    try:
        return operation()
    except Phase6OrchestrationError as error:
        status = 404 if error.code == "EPISODE_NOT_FOUND" else 409
        if error.code in {
            "PAYLOAD_OUT_OF_BOUNDS",
            "PII_OR_ANSWER_DATA_REJECTED",
            "EVENT_VERSION_UNSUPPORTED",
        }:
            status = 422
        raise HTTPException(status_code=status, detail={"code": error.code}) from error


def _owned(orchestrator: Phase6Orchestrator, episode_id: UUID, learner_id: UUID) -> None:
    record = _call(lambda: orchestrator.reconstruct(episode_id))
    if record["state"]["learner_id"] != str(learner_id):
        raise HTTPException(status_code=404, detail={"code": "EPISODE_NOT_FOUND"})


@router.post("/episodes", response_model=ChildEpisodeResponse)
def open_episode(
    body: OpenEpisodeRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    db: Session = Depends(get_db),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    if learner_id != body.learner_id:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    profile = SqlAlchemyLearnerRepository(db).get(learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    if profile.grade != 5 or profile.preferred_language != "si":
        raise HTTPException(status_code=409, detail={"code": "GRADE5_SINHALA_REQUIRED"})
    return _call(lambda: orchestrator.open_episode(**body.model_dump(), idempotency_key=key))


@router.post("/episodes/{episode_id}/before", response_model=ChildEpisodeResponse)
def answer_before(
    episode_id: UUID,
    body: AnswerRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.submit_before(
            episode_id, option_id=body.option_id, idempotency_key=key
        )
    )


@router.post("/episodes/{episode_id}/support/complete", response_model=ChildEpisodeResponse)
def complete_support(
    episode_id: UUID,
    body: SupportCompleteRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.complete_support(
            episode_id,
            duration_ms=body.duration_ms,
            steps_viewed=body.steps_viewed,
            idempotency_key=key,
        )
    )


@router.post("/episodes/{episode_id}/support/withdraw", response_model=ChildEpisodeResponse)
def withdraw_support(
    episode_id: UUID,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(lambda: orchestrator.withdraw_support(episode_id, idempotency_key=key))


@router.post("/episodes/{episode_id}/after/present", response_model=ChildEpisodeResponse)
def present_after(
    episode_id: UUID,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(lambda: orchestrator.present_after(episode_id, idempotency_key=key))


@router.post("/episodes/{episode_id}/after", response_model=ChildEpisodeResponse)
def answer_after(
    episode_id: UUID,
    body: AnswerRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.submit_after(
            episode_id, option_id=body.option_id, idempotency_key=key
        )
    )


@router.post("/episodes/{episode_id}/telemetry", response_model=TelemetryAcknowledgement)
def ingest_telemetry(
    episode_id: UUID,
    body: TelemetryBatch,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.ingest_telemetry(
            episode_id,
            batch_id=body.batch_id,
            first_sequence=body.first_sequence,
            events=tuple(row.model_dump(mode="json") for row in body.events),
            idempotency_key=key,
        )
    )


@router.get("/episodes/{episode_id}/reconstruction")
def reconstruction(
    episode_id: UUID,
    _role: None = Depends(_researcher),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    return _call(lambda: orchestrator.reconstruct(episode_id))


@router.get("/episodes/{episode_id}/export-manifest")
def export_manifest(
    episode_id: UUID,
    _role: None = Depends(_researcher),
    orchestrator: Phase6Orchestrator = Depends(get_phase6_orchestrator),
) -> dict[str, object]:
    return _call(lambda: orchestrator.export_manifest(episode_id))
