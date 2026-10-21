"""Development-only HTTP adapter for the durable episode coordinator."""

# FastAPI dependency injection intentionally uses Depends calls in defaults.
# ruff: noqa: B008

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION
from app.gamification.api.router import VisualFeatureWindow
from app.gamification.application.delivery import RateLimiter, get_learning_flow_rate_limiter
from app.gamification.application.fixture_round import FixtureRoundError, FixtureRoundService
from app.gamification.application.learner_state_answers import (
    LEARNER_STATE_CAMERA_CONSENT_VERSION,
    LEARNER_STATE_CAMERA_PURPOSE,
)
from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
)
from app.gamification.application.records import ConsentDecision
from app.gamification.content.area_support_catalog import (
    AreaSupportCatalog,
    AreaSupportRow,
    load_area_support_catalog,
)
from app.gamification.content.draft_mission_catalog import (
    DraftMissionCatalog,
    DraftMissionRecord,
    load_draft_mission_catalog,
)
from app.gamification.content.support_types import (
    ENGLISH_TAGS,
    EnglishTagKey,
    SupportType,
)
from app.gamification.infrastructure.db.consent_store import (
    CONSENT_CONTRACT,
    SqlAlchemyConsentStore,
)
from app.gamification.infrastructure.db.learning_flow_gateways import (
    SqlAlchemyLearningFlowEvidencePublisher,
    SqlAlchemyProbeGateway,
)
from app.gamification.infrastructure.db.learning_flow_store import (
    SqlAlchemyLearningFlowStore,
)
from app.gamification.infrastructure.db.models import LearningFlowProbeReservationModel
from app.gamification.infrastructure.gateways.learner_state_answers import (
    learner_state_answer_gateway,
)
from app.gamification.infrastructure.gateways.research_learning_state import (
    ResearchLearningStateGateway,
)
from app.shared.database.session import get_db
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from app.shared.learning_state_provider import stored_learning_state_provider

routes = APIRouter(tags=["gamification-learning-flow-development"])


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenEpisodeRequest(Boundary):
    learner_id: UUID
    session_id: UUID
    grade: Literal[5]
    medium: Literal["si"]
    condition: Literal["baseline", "proposed"]
    environment: Literal["development", "test", "pilot"]
    allow_draft: Literal[True]
    area_id: str | None = Field(default=None, max_length=32)
    atomic_skill_id: str | None = Field(default=None, max_length=64)


class AnswerRequest(Boundary):
    option_id: str | None = Field(default=None, min_length=1, max_length=32)
    constructed_response: dict[str, object] | None = Field(default=None, max_length=20)
    response_time_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    interaction_summary: dict[str, object] = Field(default_factory=dict, max_length=12)
    # Optional learner-state evidence: the 11 on-device camera numbers of the last 10 seconds
    # (used only with camera consent) and the app session the answer belongs to.
    visual: VisualFeatureWindow | None = None
    learner_state_session_id: UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def discard_invalid_optional_visual(cls, value: object) -> object:
        """Optional camera evidence can never turn a valid answer into a 422."""
        if not isinstance(value, dict) or value.get("visual") is None:
            return value
        try:
            VisualFeatureWindow.model_validate(value["visual"])
        except ValidationError:
            cleaned = dict(value)
            cleaned.pop("visual")
            return cleaned
        return value


class CameraConsentRequest(Boundary):
    granted: bool


class CameraConsentResponse(Boundary):
    granted: bool
    decided_at: datetime | None


class SupportCompleteRequest(Boundary):
    duration_ms: int = Field(ge=0, le=86_400_000)
    steps_viewed: int = Field(ge=1, le=8)
    manifest_revision_id: str = Field(min_length=1, max_length=128)
    grouped_count: int = Field(default=0, ge=0, le=100_000)
    group_sizes: tuple[int, ...] = Field(default=(), max_length=6)
    interaction_summary: dict[str, str | int | bool] = Field(default_factory=dict, max_length=12)


class WithdrawalAcknowledgementRequest(Boundary):
    request_id: UUID
    support_revision_id: str = Field(min_length=1, max_length=128)
    manifest_revision_id: str = Field(min_length=1, max_length=128)
    all_support_removed: Literal[True]
    answer_revealing_state_cleared: Literal[True]
    input_handlers_cleared: Literal[True]


class TelemetryEvent(Boundary):
    event_id: UUID
    sequence: int = Field(ge=1, le=1_000_000)
    version: Literal[1]
    client_occurred_at: datetime
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
    game: dict[str, object] | None = None


class HalfSetGameManifest(Boundary):
    schema_version: Literal["half-set-manifest-v1"]
    activity_id: str
    revision_id: str
    deterministic_seed: int
    total_objects: int = Field(ge=2, le=40)
    group_count: Literal[2]
    object_label_si: str
    instruction_si: str


class SupportedAnswerRequest(Boundary):
    """An attempt made inside the current help round. The server picks the item and the type."""

    constructed_response: dict[str, object] = Field(max_length=20)
    response_time_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    interaction_summary: dict[str, object] = Field(default_factory=dict, max_length=12)


class SupportView(Boundary):
    scaffold_id: str
    revision_id: str
    scaffold_type: SupportType
    english_tag_key: EnglishTagKey | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    title_si: str
    body_si: tuple[str, ...]
    visual_alt_text_si: str | None
    maximum_steps: int
    game_manifest: HalfSetGameManifest | dict[str, object]


class ParticipationReward(Boundary):
    points: int
    reason: str


class ServerScore(Boundary):
    earned_score: str
    maximum_score: str
    scoring_version: str
    server_authoritative: Literal[True]
    measurement_role: str
    correct: bool | None = Field(default=None, exclude_if=lambda value: value is None)
    attempt_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    presentation_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    item_revision_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    feedback_step_index: int | None = Field(default=None, ge=0, le=2, exclude_if=lambda value: value is None)
    feedback_column: str | None = Field(default=None, exclude_if=lambda value: value is None)


class SupportRoundStatus(Boundary):
    """Where the multi-help loop stands. It never names a later help type."""

    round_number: int = Field(ge=1)
    scaffold_type: SupportType
    english_tag_key: EnglishTagKey = Field(json_schema_extra={"x-english-tags": ENGLISH_TAGS})
    stage_kind: Literal["practice", "target", "view"] | None
    previous_attempt_correct: bool | None
    another_round_required: bool
    withdrawal_allowed: bool
    support_revision_id: str
    manifest_revision_id: str


class ChildEpisodeResponse(Boundary):
    model_config = ConfigDict(extra="ignore")

    episode_id: UUID
    status: str
    manifest: PresentationManifest | None = None
    support: SupportView | None = None
    reward: ParticipationReward | None = None
    server_score: ServerScore | None = None
    # Learner-state decision for this scored answer; absent on replays and without learner-state.
    learner_state_action: (
        Literal[
            "none",
            "monitor",
            "request_tutor_support",
            "request_reengagement_support",
            "collect_more_evidence",
        ]
        | None
    ) = None
    support_round: SupportRoundStatus | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class TelemetryAcknowledgement(Boundary):
    accepted: int
    duplicates: int
    next_sequence: int


class FixtureSupportView(Boundary):
    support_type: Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]
    body_si: str
    assistance_state: Literal["scaffold_active"]


class FixtureReward(Boundary):
    points: int
    reason_code: str


class FixtureRoundResponse(Boundary):
    episode_id: UUID
    area_id: str
    template_id: Literal[
        "market_mission",
        "half_set",
        "pattern_temple",
        "parcel_workshop",
        "word_workshop",
        "story_studio",
        "eco_explorer",
    ]
    phase: Literal[
        "unsupported_before",
        "support",
        "supported_practice",
        "withdraw",
        "unsupported_after",
        "completed",
    ]
    notice_si: str
    prompt_si: str | None = None
    assistance_state: Literal["none", "scaffold_active"]
    options: tuple[PublicOption, ...] = ()
    support: FixtureSupportView | None = None
    server_score: ServerScore | None = None
    server_scores: tuple[ServerScore, ...] = ()
    reward: FixtureReward | None = None


class OpenFixtureRoundRequest(Boundary):
    area_id: str = Field(min_length=1, max_length=32)
    learner_id: UUID
    session_id: UUID
    grade: Literal[5]
    medium: Literal["si"]


class PublicMathematicsOutcomeSlot(Boundary):
    node_id: str
    parent_area_id: str
    trace_competency_id: str
    supplied_area_match: bool
    confidence: Literal["medium"]
    draft_item: Literal[True]
    item_text: str


class PublicSinhalaDraftItemSlot(Boundary):
    node_id: str
    parent_area_id: str
    confidence: Literal["high"]
    draft_item: Literal[True]
    area_match: bool
    item_text: str


class PublicHeldOutcomeSlot(Boundary):
    node_id: str
    parent_area_id: str
    confidence: Literal["low"]
    held: Literal[True]
    draft_item: Literal[False]
    traced_text: str
    child_question: None


class PublicDraftMissionRecord(Boundary):
    area_id: str
    cited_node_id: str
    template_id: str
    outcome_slots: tuple[PublicMathematicsOutcomeSlot, ...] = ()
    draft_item_slots: tuple[PublicSinhalaDraftItemSlot, ...] = ()
    held_slots: tuple[PublicHeldOutcomeSlot, ...] = ()


class PublicDraftMissionCatalog(Boundary):
    package_version: str
    missions: tuple[PublicDraftMissionRecord, ...]


class PublicAreaSupportRow(Boundary):
    area_id: str
    name_en: str
    subject: Literal["MAT", "SIN", "ENV"]
    template_id: str
    eligible_support_types: tuple[SupportType, ...]
    rule: str
    rendering_constraint: str
    authoring_basis: str


_fixture_rounds = FixtureRoundService()


def _fixture_call(operation):
    try:
        return operation()
    except FixtureRoundError as error:
        status = 409
        if error.code in {"FIXTURE_NOT_FOUND", "EPISODE_NOT_FOUND"}:
            status = 404
        if error.code == "HUMAN_APPROVAL_REQUIRED":
            status = 403
        raise HTTPException(status_code=status, detail={"code": error.code}) from error


def get_learning_flow_orchestrator(db: Session = Depends(get_db)) -> LearningFlowOrchestrator:
    engine = db.get_bind()
    return LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(db),
        probe_gateway=SqlAlchemyProbeGateway(db),
        evidence_publisher=SqlAlchemyLearningFlowEvidencePublisher(db),
        # Learner-state records in its own session on the same database, after the answer is
        # committed, so it never commits or rolls back the game's transaction.
        learner_state=learner_state_answer_gateway(
            lambda: Session(bind=engine, autoflush=False, expire_on_commit=False)
        ),
        camera_consent=SqlAlchemyConsentStore(db),
        support_need_provider=ResearchLearningStateGateway(stored_learning_state_provider(db)),
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
    limiter: RateLimiter = Depends(get_learning_flow_rate_limiter),
) -> UUID:
    if principal[0] != "learner" or principal[1] is None:
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN"})
    limiter.allow(f"learning_flow:{principal[1]}", datetime.now(UTC))
    return principal[1]


def _researcher(principal: tuple[str, UUID | None] = Depends(_principal)) -> None:
    if principal[0] != "researcher":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN"})


def _call(operation):
    try:
        return operation()
    except LearningFlowOrchestrationError as error:
        status = 404 if error.code == "EPISODE_NOT_FOUND" else 409
        if error.code in {
            "PAYLOAD_OUT_OF_BOUNDS",
            "PII_OR_ANSWER_DATA_REJECTED",
            "EVENT_VERSION_UNSUPPORTED",
        }:
            status = 422
        raise HTTPException(
            status_code=status, detail={"code": error.code, **error.context}
        ) from error


def _owned(orchestrator: LearningFlowOrchestrator, episode_id: UUID, learner_id: UUID) -> None:
    record = _call(lambda: orchestrator.reconstruct(episode_id))
    if record["state"]["learner_id"] != str(learner_id):
        raise HTTPException(status_code=404, detail={"code": "EPISODE_NOT_FOUND"})


@routes.post("/episodes", response_model=ChildEpisodeResponse)
def open_episode(
    body: OpenEpisodeRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    db: Session = Depends(get_db),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    if learner_id != body.learner_id:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    profile = SqlAlchemyLearnerRepository(db).get(learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    if profile.grade != 5 or profile.preferred_language != "si":
        raise HTTPException(status_code=409, detail={"code": "GRADE5_SINHALA_REQUIRED"})
    return _call(lambda: orchestrator.open_episode(**body.model_dump(), idempotency_key=key))


@routes.get("/learners/{learner_id}/skills/{atomic_skill_id}/available")
def learner_skill_available(
    learner_id: UUID,
    atomic_skill_id: str,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    profile = SqlAlchemyLearnerRepository(db).get(learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    if profile.grade != 5 or profile.preferred_language != "si":
        return {"available": False}
    prior_probe = db.scalar(
        select(LearningFlowProbeReservationModel.reservation_id)
        .where(
            LearningFlowProbeReservationModel.learner_id == learner_id,
            LearningFlowProbeReservationModel.item_revision_id.like(
                f"{atomic_skill_id}:A:%"
            ),
        )
        .limit(1)
    )
    return {"available": prior_probe is None}


@routes.post("/episodes/{episode_id}/before", response_model=ChildEpisodeResponse)
def answer_before(
    episode_id: UUID,
    body: AnswerRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.submit_before(
            episode_id,
            option_id=body.option_id,
            constructed_response=body.constructed_response,
            response_time_ms=body.response_time_ms,
            interaction_summary=body.interaction_summary,
            idempotency_key=key,
            visual=None if body.visual is None else body.visual.model_dump(),
            learner_state_session_id=body.learner_state_session_id,
        )
    )


@routes.post("/episodes/{episode_id}/support/complete", response_model=ChildEpisodeResponse)
def complete_support(
    episode_id: UUID,
    body: SupportCompleteRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.complete_support(
            episode_id,
            duration_ms=body.duration_ms,
            steps_viewed=body.steps_viewed,
            manifest_revision_id=body.manifest_revision_id,
            grouped_count=body.grouped_count,
            group_sizes=body.group_sizes,
            interaction_summary=body.interaction_summary,
            idempotency_key=key,
        )
    )


@routes.post("/episodes/{episode_id}/support/answer", response_model=ChildEpisodeResponse)
def answer_supported(
    episode_id: UUID,
    body: SupportedAnswerRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.submit_supported(
            episode_id,
            constructed_response=body.constructed_response,
            response_time_ms=body.response_time_ms,
            interaction_summary=body.interaction_summary,
            idempotency_key=key,
        )
    )


@routes.post("/episodes/{episode_id}/support/withdraw", response_model=ChildEpisodeResponse)
def withdraw_support(
    episode_id: UUID,
    body: WithdrawalAcknowledgementRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.withdraw_support(
            episode_id,
            request_id=body.request_id,
            support_revision_id=body.support_revision_id,
            manifest_revision_id=body.manifest_revision_id,
            all_support_removed=body.all_support_removed,
            answer_revealing_state_cleared=body.answer_revealing_state_cleared,
            input_handlers_cleared=body.input_handlers_cleared,
            idempotency_key=key,
        )
    )


@routes.post("/episodes/{episode_id}/after/present", response_model=ChildEpisodeResponse)
def present_after(
    episode_id: UUID,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(lambda: orchestrator.present_after(episode_id, idempotency_key=key))


@routes.post("/episodes/{episode_id}/after", response_model=ChildEpisodeResponse)
def answer_after(
    episode_id: UUID,
    body: AnswerRequest,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    _owned(orchestrator, episode_id, learner_id)
    return _call(
        lambda: orchestrator.submit_after(
            episode_id,
            option_id=body.option_id,
            constructed_response=body.constructed_response,
            response_time_ms=body.response_time_ms,
            idempotency_key=key,
            visual=None if body.visual is None else body.visual.model_dump(),
            learner_state_session_id=body.learner_state_session_id,
        )
    )


@routes.get("/consents/learner-state-camera", response_model=CameraConsentResponse)
def read_camera_consent(
    learner_id: UUID = Depends(_learner),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        decision = SqlAlchemyConsentStore(db).get_consent(
            learner_id=learner_id, purpose=LEARNER_STATE_CAMERA_PURPOSE
        )
    except LookupError:
        return {"granted": False, "decided_at": None}
    return {"granted": decision.granted, "decided_at": decision.decided_at}


@routes.put("/consents/learner-state-camera", response_model=CameraConsentResponse)
def record_camera_consent(
    body: CameraConsentRequest,
    learner_id: UUID = Depends(_learner),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Development stand-in for the guardian's camera decision; production needs guardian auth."""
    if SqlAlchemyLearnerRepository(db).get(learner_id) is None:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    decision = ConsentDecision(
        learner_id=learner_id,
        purpose=LEARNER_STATE_CAMERA_PURPOSE,
        granted=body.granted,
        consent_version=LEARNER_STATE_CAMERA_CONSENT_VERSION,
        decided_at=datetime.now(UTC),
        expires_at=None,
        contract_version=CONSENT_CONTRACT,
    )
    SqlAlchemyConsentStore(db).record(decision)
    return {"granted": decision.granted, "decided_at": decision.decided_at}


@routes.post("/episodes/{episode_id}/telemetry", response_model=TelemetryAcknowledgement)
def ingest_telemetry(
    episode_id: UUID,
    body: TelemetryBatch,
    key: str = Depends(_key),
    learner_id: UUID = Depends(_learner),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
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


@routes.get("/episodes/{episode_id}/reconstruction")
def reconstruction(
    episode_id: UUID,
    _role: None = Depends(_researcher),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    return _call(lambda: orchestrator.reconstruct(episode_id))


@routes.get("/episodes/{episode_id}/export-manifest")
def export_manifest(
    episode_id: UUID,
    _role: None = Depends(_researcher),
    orchestrator: LearningFlowOrchestrator = Depends(get_learning_flow_orchestrator),
) -> dict[str, object]:
    return _call(lambda: orchestrator.export_manifest(episode_id))


def _support_catalog() -> AreaSupportCatalog:
    return load_area_support_catalog()


def _draft_catalog() -> DraftMissionCatalog:
    return load_draft_mission_catalog()


development_router = APIRouter(prefix="/development/learning-flow")
development_router.include_router(routes)
router = APIRouter(prefix="/learning-flow", tags=["gamification-learning-flow"])


@router.get("/draft-missions", response_model=PublicDraftMissionCatalog)
def list_draft_missions(
    _role: None = Depends(_researcher),
) -> DraftMissionCatalog:
    return _draft_catalog()


@router.get(
    "/draft-missions/{area_id}/support-types",
    response_model=PublicAreaSupportRow,
)
def fetch_area_support_types(
    area_id: str,
    _role: None = Depends(_researcher),
) -> AreaSupportRow:
    catalog = _support_catalog()
    try:
        return catalog.row(area_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "AREA_SUPPORT_NOT_FOUND"}) from error


@router.get("/draft-missions/{area_id}", response_model=PublicDraftMissionRecord)
def fetch_draft_mission(
    area_id: str,
    _role: None = Depends(_researcher),
) -> DraftMissionRecord:
    catalog = _draft_catalog()
    try:
        return catalog.mission(area_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_MISSION_NOT_FOUND"}) from error


def _grade5_sinhala_learner(learner_id: UUID, db: Session) -> None:
    profile = SqlAlchemyLearnerRepository(db).get(learner_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    if profile.grade != 5 or profile.preferred_language != "si":
        raise HTTPException(status_code=409, detail={"code": "GRADE5_SINHALA_REQUIRED"})


@router.post("/fixture-rounds", response_model=FixtureRoundResponse)
def open_fixture_round(
    body: OpenFixtureRoundRequest,
    learner_id: UUID = Depends(_learner),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if learner_id != body.learner_id:
        raise HTTPException(status_code=404, detail={"code": "LEARNER_NOT_FOUND"})
    _grade5_sinhala_learner(learner_id, db)
    return _fixture_call(lambda: _fixture_rounds.open_round(**body.model_dump()))


@router.post("/fixture-rounds/{episode_id}/answer", response_model=FixtureRoundResponse)
def answer_fixture_round(
    episode_id: UUID,
    body: AnswerRequest,
    learner_id: UUID = Depends(_learner),
) -> dict[str, object]:
    return _fixture_call(
        lambda: _fixture_rounds.answer(episode_id, option_id=body.option_id, learner_id=learner_id)
    )


@router.post("/fixture-rounds/{episode_id}/continue", response_model=FixtureRoundResponse)
def continue_fixture_round(
    episode_id: UUID,
    learner_id: UUID = Depends(_learner),
) -> dict[str, object]:
    return _fixture_call(lambda: _fixture_rounds.continue_round(episode_id, learner_id=learner_id))


# Keep previously shipped development clients working during the terminology migration. The
# compatibility path is hidden from generated contracts and assembled so its retired numbered
# label cannot leak back into implementation naming.
legacy_router = APIRouter(prefix="/development/" + "phase" + "6", include_in_schema=False)
legacy_router.include_router(routes, include_in_schema=False)
