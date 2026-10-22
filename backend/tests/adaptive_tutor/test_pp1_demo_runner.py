"""PP1 runner reliability: stop rules, failed generations, transcript correctness (no network)."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.api.router import get_research_tutor_service
from app.adaptive_tutor.application.context_assembly import (
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    SupportNeedResult,
    TutorContextAssembler,
)
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.generation import DeterministicFakeLlmProvider
from app.adaptive_tutor.application.orchestration import TutorOrchestrator
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure.assessment_evidence import (
    LedgerAssessmentEvidenceProvider,
)
from app.adaptive_tutor.infrastructure.gemini import GeminiGenerationConfig, GeminiLlmProvider
from app.adaptive_tutor.infrastructure.knowledge_tracing_mastery import (
    KnowledgeTracingMasteryProvider,
)
from app.adaptive_tutor.infrastructure.research_sessions import (
    CONTROLLED_ANNOTATION_SOURCE,
    ExperimentalHintGenerator,
    ResearchTutorService,
)
from app.adaptive_tutor.infrastructure.tutor_assessment import SqlAlchemyTutorAssessmentRepository
from app.adaptive_tutor.infrastructure.tutor_history import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryProvider,
)
from app.config import Settings, get_settings
from app.knowledge_tracing.application.mastery import MasteryResult, MasteryStatus
from app.knowledge_tracing.domain.mastery import MasterySnapshot, SkillEstimate
from app.main import app
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel
from scripts.pp1_multiturn_demo import (
    ATTEMPTS,
    REHEARSAL_PROVIDER_NAME,
    SCRIPTED_SCORING_VERSION,
    CallLog,
    FakeRehearsalProvider,
    RunGuard,
    build_report,
    execute,
    markdown,
)

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000101")
RESEARCHER_ID = "00000000-0000-4000-8000-000000000102"
POLICY = "pp1-test-severity-v1"
KEY = "test-research-key"
SOURCE = EvidenceSource(source_id="MOCKED:test:pp1-runner", origin=EvidenceOrigin.SYNTHETIC)


def step(status: str = "GENERATED", reason: str | None = None) -> dict[str, object]:
    return {"experimental_generation_status": status, "experimental_provider_reason_code": reason}


UNAVAILABLE = step("PROVIDER_UNAVAILABLE", "PROVIDER_TEMPORARILY_UNAVAILABLE")


def test_guard_stops_after_two_consecutive_unavailability_errors() -> None:
    guard = RunGuard()
    assert guard.observe(step(), first=True) is None
    assert guard.observe(UNAVAILABLE, first=False) is None
    assert guard.observe(UNAVAILABLE, first=False) == (
        "two consecutive temporary provider unavailability errors or timeouts"
    )


def test_guard_resets_the_unavailability_streak_after_a_success() -> None:
    guard = RunGuard()
    for observed in (step(), UNAVAILABLE, step(), UNAVAILABLE, step()):
        assert guard.observe(observed, first=False) is None


@pytest.mark.parametrize(
    ("observed", "first", "expected"),
    [
        (UNAVAILABLE, True, "first Gemini call did not generate a draft"),
        (step("PROVIDER_ERROR", "AUTHENTICATION_FAILED"), False, "fatal provider failure"),
        (step("PROVIDER_ERROR", "MODEL_NOT_FOUND"), False, "fatal provider failure"),
    ],
)
def test_guard_stops_immediately_on_first_or_fatal_failures(
    observed: dict[str, object], first: bool, expected: str
) -> None:
    assert (RunGuard().observe(observed, first=first) or "").startswith(expected)


def test_guard_treats_mixed_unavailability_and_timeouts_as_one_streak() -> None:
    timeout = step("PROVIDER_UNAVAILABLE", "NETWORK_OR_TIMEOUT")
    guard = RunGuard()
    assert guard.observe(UNAVAILABLE, first=False) is None
    assert guard.observe(timeout, first=False) is not None


def test_guard_counts_rate_limits_and_repeated_timeouts() -> None:
    limited = step("PROVIDER_UNAVAILABLE", "RATE_LIMITED")
    timeout = step("PROVIDER_UNAVAILABLE", "NETWORK_OR_TIMEOUT")
    guard = RunGuard()
    assert guard.observe(limited, first=False) is None
    assert guard.observe(UNAVAILABLE, first=False) is not None
    guard = RunGuard()
    assert guard.observe(timeout, first=False) is None
    assert guard.observe(step(), first=False) is None
    assert guard.observe(timeout, first=False) == "repeated timeouts"


class ServerError(Exception):
    """Shape of google.genai.errors.ServerError for status mapping."""

    def __init__(self, code: int) -> None:
        super().__init__("provider detail")
        self.code = code


class ScriptedGeminiModels:
    """Succeeds or raises 503 per call, and logs calls like the runner's wrappers."""

    def __init__(self, outcomes: list[bool], log: CallLog) -> None:
        self._outcomes = iter(outcomes)
        self._log = log

    def generate_content(self, **_: object) -> object:
        ok = next(self._outcomes)
        self._log.calls.append({"seconds": 0.0, "outcome": "OK" if ok else "ServerError"})
        if not ok:
            raise ServerError(503)
        return SimpleNamespace(text="Have another go.", prompt_feedback=None, candidates=[])


class MatchedMapper:
    def map(self, request: object) -> SkillMappingResult:
        return SkillMappingResult(
            status=SkillMappingStatus.MATCHED,
            intent=LearningIntent.EXPLANATION_REQUEST,
            skill_id="MAT-FRC",
            confidence=0.95,
            clarification_needed=False,
        )


class ColdStartContext:
    """Same values as the PP1 cold-start defaults (mastery 0.0, support need 0.0)."""

    source = SOURCE

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        return LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(id=learner_id, grade=5, preferred_language="en"),
        )

    def get_mastery(self, request: object) -> MasteryResult:
        return MasteryResult(
            learner_id=request.learner_id,  # type: ignore[attr-defined]
            skill_id=request.skill_id,  # type: ignore[attr-defined]
            status=MasteryStatus.AVAILABLE,
            mastery=0.0,
        )

    def get_support_need(self, request: object) -> SupportNeedResult:
        return SupportNeedResult(status=EvidenceStatus.AVAILABLE, support_need=0.0)


@pytest.fixture
def harness() -> Iterator[tuple[Session, TestClient]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
        db.commit()
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="sqlite://",
            tutor_api_mode="research-local",
            tutor_research_access_key=KEY,
            tutor_researcher_id=RESEARCHER_ID,
        )
        yield db, TestClient(app, headers={"X-Tutor-Research-Key": KEY})
        app.dependency_overrides.clear()


def install_service(
    db: Session,
    outcomes: list[bool],
    *,
    mastery_provider: object | None = None,
    draft_provider: Callable[[CallLog], object] | None = None,
) -> CallLog:
    log = CallLog()
    context = ColdStartContext()
    assessments = SqlAlchemyTutorAssessmentRepository(db)
    history = SqlAlchemyTutorHistoryRepository(db)
    orchestrator = TutorOrchestrator(
        skill_mapper=MatchedMapper(),
        skill_mapper_source=SOURCE,
        context_assembler=TutorContextAssembler(
            learner_provider=context,
            mastery_provider=mastery_provider or context,
            support_need_provider=context,
            assessment_provider=LedgerAssessmentEvidenceProvider(
                assessments,
                valid_skill_ids={"MAT-FRC"},
                eligible_scorer_sources={CONTROLLED_ANNOTATION_SOURCE},
                eligible_severity_policy_versions={POLICY},
                controlled_research=True,
            ),
            history_provider=TutorHistoryProvider(history),
            valid_skill_ids={"MAT-FRC"},
        ),
        controller=ScaffoldingController(),
        llm_provider=DeterministicFakeLlmProvider(),
        valid_skill_ids={"MAT-FRC"},
        decision_only=True,
    )
    service = ResearchTutorService(
        skill_mapper=MatchedMapper(),
        orchestrator=orchestrator,
        assessments=assessments,
        history=history,
        eligible_severity_policy_versions=frozenset({POLICY}),
        experimental_generator=ExperimentalHintGenerator(
            draft_provider(log)
            if draft_provider is not None
            else GeminiLlmProvider(
                GeminiGenerationConfig(api_key="test-key", model="gemini-test"),
                client=SimpleNamespace(models=ScriptedGeminiModels(outcomes, log)),
            ),
            "UNREVIEWED researcher-authored Fractions content.",
            lambda _learner_id: 5,
        ),
    )
    app.dependency_overrides[get_research_tutor_service] = lambda: service
    return log


def run_scenario(db: Session, http: TestClient, outcomes: list[bool], limit: int | None = 7):
    log = install_service(db, outcomes)
    execution = execute(
        http, db, log, learner_id=LEARNER_ID, severity_policy=POLICY, call_limit=limit
    )
    return log, execution


def test_runner_stops_after_two_consecutive_503s(harness: tuple[Session, TestClient]) -> None:
    db, http = harness
    log, execution = run_scenario(db, http, [True, True, False, False, True, True, True])

    assert (
        execution.stopped == "two consecutive temporary provider unavailability errors or timeouts"
    )
    assert len(log.calls) == 4
    assert [s["step"] for s in execution.steps] == ["question", "a1", "a2", "a3"]
    assert [s["draft_presented"] for s in execution.steps] == [True, True, False, False]
    assert sum(e["event_type"] == "RESEARCH_PRESENTATION" for e in execution.events) == 2


def test_failed_draft_is_not_previous_assistance(harness: tuple[Session, TestClient]) -> None:
    db, http = harness
    # a3's L3 draft fails; at a4 the last *shown* hint is a2's L2, so escalation is L2 -> L3,
    # not L3 -> L4 as if the failed L3 hint had been presented.
    _, execution = run_scenario(db, http, [True, True, True, False, True, True, True])

    levels = {s["step"]: s["assistance_level"] for s in execution.steps}
    assert levels["a3"] == "L3"
    assert execution.steps[3]["draft_presented"] is False
    assert levels["a4"] == "L3"
    assert "ESCALATION_JUSTIFIED" in execution.steps[4]["controller_reason_codes"]


def test_call_limit_stops_before_making_another_request(
    harness: tuple[Session, TestClient],
) -> None:
    db, http = harness
    log, execution = run_scenario(db, http, [True] * 7, limit=3)

    assert len(log.calls) == 3
    assert execution.stopped == "provider call limit reached (3)"


def test_complete_transcript_is_correct_and_sanitized(harness: tuple[Session, TestClient]) -> None:
    db, http = harness
    log, execution = run_scenario(db, http, [True] * 7)
    report = build_report(
        execution,
        log,
        provider="fake",
        provider_label="FAKE PROVIDER REHEARSAL — not Gemini output",
        thinking_level="LOW",
        database="sqlite",
        call_limit=7,
    )

    assert [s["assistance_level"] for s in report["steps"]] == [
        "L0",
        "L2",
        "L2",
        "L3",
        "L4",
        "L3",
        "L0",
    ]
    assert all(report["invariants"].values()), report["invariants"]
    assert report["provider_call_count"] == len(ATTEMPTS) + 1
    text = markdown(report) + str(report)
    assert str(LEARNER_ID) not in text
    assert "session_token" not in text and KEY not in text
    assert "EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS" in text


def test_partial_transcript_reports_failures_without_breaking_invariants(
    harness: tuple[Session, TestClient],
) -> None:
    db, http = harness
    log, execution = run_scenario(db, http, [True, True, False, False])
    report = build_report(
        execution,
        log,
        provider="gemini",
        provider_label="google-gemini test",
        thinking_level="LOW",
        database="sqlite",
        call_limit=7,
    )

    invariants = report["invariants"]
    assert invariants["scenario_completed"] is False
    assert invariants["presentation_only_for_generated_drafts"] is True
    assert invariants["no_learner_delivery_events"] is True
    assert report["steps"][2]["experimental_provider_reason_code"] == (
        "PROVIDER_TEMPORARILY_UNAVAILABLE"
    )
    assert report["stopped_early"] in markdown(report)


class SnapshotService:
    """Stands in for the KT MasteryService: one snapshot, no model or database."""

    def __init__(self, mastery: float | None) -> None:
        self._mastery = mastery

    def current(self, learner_id: UUID) -> MasterySnapshot:
        return MasterySnapshot(
            id=1,
            learner_id=learner_id,
            computed_at=datetime(2026, 10, 22, tzinfo=UTC),
            model_version="kt-test",
            n_attempts=3,
            skills=(SkillEstimate("MAT-FRC", self._mastery, 3),),
        )


def ask_once(http: TestClient) -> dict[str, object]:
    api = "/api/v1/adaptive-tutor/research"
    started = http.post(f"{api}/sessions", json={"learner_id": str(LEARNER_ID)}).json()
    response = http.post(
        f"{api}/sessions/{started['session_id']}/questions",
        json={"student_message": "Why is 1/2 equal to 2/4?", "response_language": "en"},
        headers={"X-Tutor-Research-Session": started["session_token"]},
    )
    response.raise_for_status()
    return response.json()


def mastery_evidence(body: dict[str, object]) -> dict[str, object]:
    return next(
        item
        for item in body["context_provenance"]  # type: ignore[union-attr]
        if item["input"] == "MASTERY"
    )


@pytest.mark.parametrize(
    ("kt_value", "origin", "source_id"),
    [
        (0.625, "REAL", "knowledge-tracing:mastery-service"),
        (None, "SYNTHETIC", "adaptive-tutor:experimental-cold-start-mastery-default"),
    ],
)
def test_api_reports_mastery_provenance_per_value(
    harness: tuple[Session, TestClient],
    kt_value: float | None,
    origin: str,
    source_id: str,
) -> None:
    db, http = harness
    install_service(
        db,
        [True],
        mastery_provider=KnowledgeTracingMasteryProvider(
            SnapshotService(kt_value),  # type: ignore[arg-type]
            {"MAT-FRC"},
            cold_start_default=0.0,
        ),
    )

    evidence = mastery_evidence(ask_once(http))

    assert (evidence["origin"], evidence["source_id"]) == (origin, source_id)


def test_rehearsal_drafts_are_never_labelled_as_gemini(
    harness: tuple[Session, TestClient],
) -> None:
    db, http = harness
    log = install_service(db, [], draft_provider=FakeRehearsalProvider)
    execution = execute(
        http, db, log, learner_id=LEARNER_ID, severity_policy=POLICY, call_limit=None
    )
    report = build_report(
        execution,
        log,
        provider="fake",
        provider_label="FAKE PROVIDER REHEARSAL — not Gemini output",
        thinking_level="",
        database="sqlite",
        call_limit=None,
    )

    names = {step["experimental_provider_name"] for step in report["steps"]}
    assert names == {REHEARSAL_PROVIDER_NAME}
    assert "google-gemini" not in str(report)
    assert all(
        step["experimental_response_text"].startswith("[FAKE PROVIDER — NOT GEMINI]")
        for step in report["steps"]
    )


def test_scripted_attempts_are_persisted_and_reported_as_scripted(
    harness: tuple[Session, TestClient],
) -> None:
    db, http = harness
    log = install_service(db, [], draft_provider=FakeRehearsalProvider)
    execution = execute(
        http, db, log, learner_id=LEARNER_ID, severity_policy=POLICY, call_limit=None
    )
    report = build_report(
        execution,
        log,
        provider="fake",
        provider_label="FAKE PROVIDER REHEARSAL — not Gemini output",
        thinking_level="",
        database="sqlite",
        call_limit=None,
    )

    rows = db.execute(
        text("select distinct scoring_version, severity_category from tutor_assessment_attempts")
    ).all()
    assert {row.scoring_version for row in rows} == {SCRIPTED_SCORING_VERSION}
    assert "RESEARCHER_ANNOTATED_ERROR" not in {row.severity_category for row in rows}
    assert report["attempt_source"].startswith("SCRIPTED_SCENARIO")
    assert "not observed or reviewed student work" in markdown(report)


@pytest.mark.parametrize(
    ("provider", "accepted"),
    [
        (FakeRehearsalProvider(CallLog()), True),
        (DeterministicFakeLlmProvider(), False),
    ],
)
def test_only_gemini_or_the_labelled_rehearsal_provider_may_draft(
    provider: object, accepted: bool
) -> None:
    def build() -> ExperimentalHintGenerator:
        return ExperimentalHintGenerator(
            provider,  # type: ignore[arg-type]
            "UNREVIEWED researcher-authored Fractions content.",
            lambda _learner_id: 5,
        )

    if accepted:
        build()
    else:
        with pytest.raises(ValueError, match="rehearsal provider"):
            build()
