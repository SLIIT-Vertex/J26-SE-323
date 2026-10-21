"""Server-owned sessions for the controlled synthetic browser demonstration."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Lock
from uuid import UUID, uuid4

from app.adaptive_tutor.application.generation import GenerationPrompt, LlmProviderUnavailableError
from app.adaptive_tutor.application.orchestration import TutorWorkflowRequest, TutorWorkflowResult
from app.adaptive_tutor.application.verification import (
    DeterministicFakeSemanticVerifier,
    SemanticVerificationResult,
    VerificationCheckOutcome,
)
from app.adaptive_tutor.infrastructure.offline_pipeline import PreInteractionFixture
from app.adaptive_tutor.infrastructure.synthetic_context import (
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.adaptive_tutor.infrastructure.synthetic_orchestration import (
    build_controlled_tutor_orchestrator,
)


class DemoScenarioId(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"
    L6_BLOCKED = "L6_BLOCKED_NO_APPROVED_CURRICULUM"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_INDETERMINATE = "VERIFICATION_INDETERMINATE"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    MAPPER_ABSTENTION = "SKILL_MAPPER_ABSTENTION"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True, slots=True)
class DemoScenario:
    scenario_id: DemoScenarioId
    title: str
    fixture_id: str
    example_explanation: str | None = None


SCENARIOS = (
    DemoScenario(
        DemoScenarioId.L0, "L0 — Pre-interaction", "AT-V1-001", "Try the problem once yourself."
    ),
    DemoScenario(
        DemoScenarioId.L1,
        "L1 — Metacognitive prompt",
        "AT-V1-002",
        "What strategy could you try first?",
    ),
    DemoScenario(
        DemoScenarioId.L2,
        "L2 — Conceptual hint",
        "AT-V1-003",
        "Think about the main idea behind the problem.",
    ),
    DemoScenario(
        DemoScenarioId.L3,
        "L3 — Targeted hint",
        "AT-V1-006",
        "Identify the next useful step, then pause.",
    ),
    DemoScenario(
        DemoScenarioId.L4,
        "L4 — Guided steps",
        "AT-V1-010",
        "Start with one step and check it before continuing.",
    ),
    DemoScenario(
        DemoScenarioId.L5,
        "L5 — Analogous example",
        "AT-V1-011",
        "In a different example, two groups of three make six.",
    ),
    DemoScenario(
        DemoScenarioId.L6,
        "L6 — Synthetic explanation",
        "AT-V1-012",
        "This is a separately authored synthetic example explanation.",
    ),
    DemoScenario(DemoScenarioId.L6_BLOCKED, "L6 — Blocked real curriculum", "AT-V1-012"),
    DemoScenario(DemoScenarioId.VERIFICATION_FAILED, "Verification failure", "AT-V1-001"),
    DemoScenario(
        DemoScenarioId.VERIFICATION_INDETERMINATE, "Verification indeterminate", "AT-V1-001"
    ),
    DemoScenario(DemoScenarioId.MISSING_CONTEXT, "Missing context", "AT-V1-001"),
    DemoScenario(DemoScenarioId.MAPPER_ABSTENTION, "Skill Mapper abstention", "AT-V1-001"),
    DemoScenario(DemoScenarioId.PROVIDER_FAILURE, "Provider failure", "AT-V1-001"),
)
_SCENARIOS = {item.scenario_id: item for item in SCENARIOS}


class DemoSessionError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class DemoInteraction:
    interaction_id: UUID
    sequence: int
    occurred_at: datetime
    result: TutorWorkflowResult


@dataclass(slots=True)
class DemoSession:
    session_id: UUID
    token_digest: str
    scenario: DemoScenario
    created_at: datetime
    expires_at: datetime
    interactions: list[DemoInteraction] = field(default_factory=list)


class SyntheticDemoSessionStore:
    """Small process-local store; raw questions and generated drafts are never retained."""

    def __init__(self, *, lifetime: timedelta = timedelta(minutes=30)) -> None:
        if lifetime <= timedelta(0):
            raise ValueError("session lifetime must be positive")
        self._lifetime = lifetime
        self._sessions: dict[UUID, DemoSession] = {}
        self._lock = Lock()

    def start(
        self, scenario_id: DemoScenarioId, *, now: datetime | None = None
    ) -> tuple[DemoSession, str]:
        current = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        session = DemoSession(
            session_id=uuid4(),
            token_digest=_digest(token),
            scenario=_SCENARIOS[scenario_id],
            created_at=current,
            expires_at=current + self._lifetime,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session, token

    def submit(
        self,
        session_id: UUID,
        token: str,
        *,
        student_message: str,
        response_language: str,
        now: datetime | None = None,
    ) -> DemoInteraction:
        with self._lock:
            session = self._require(session_id, token, now)
            result = _run_scenario(session.scenario, student_message, response_language)
            interaction = DemoInteraction(
                interaction_id=uuid4(),
                sequence=len(session.interactions) + 1,
                occurred_at=now or datetime.now(UTC),
                result=result,
            )
            session.interactions.append(interaction)
            return interaction

    def history(
        self, session_id: UUID, token: str, *, now: datetime | None = None
    ) -> tuple[DemoInteraction, ...]:
        with self._lock:
            return tuple(self._require(session_id, token, now).interactions)

    def get(self, session_id: UUID, token: str, *, now: datetime | None = None) -> DemoSession:
        with self._lock:
            return self._require(session_id, token, now)

    def end(self, session_id: UUID, token: str, *, now: datetime | None = None) -> None:
        with self._lock:
            self._require(session_id, token, now)
            del self._sessions[session_id]

    def _require(self, session_id: UUID, token: str, now: datetime | None) -> DemoSession:
        session = self._sessions.get(session_id)
        if session is None or not hmac.compare_digest(session.token_digest, _digest(token)):
            raise DemoSessionError("unknown or unauthorized demo session")
        if (now or datetime.now(UTC)) >= session.expires_at:
            del self._sessions[session_id]
            raise DemoSessionError("expired demo session")
        return session


@dataclass
class _SequenceLlm:
    responses: list[str | Exception]
    name: str = "synthetic-demo-sequence"
    calls: int = 0

    def generate(self, prompt: GenerationPrompt) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


def _run_scenario(
    scenario: DemoScenario,
    student_message: str,
    response_language: str,
) -> TutorWorkflowResult:
    mode = (
        SyntheticFixtureMode.COLD_START
        if scenario.scenario_id is DemoScenarioId.MISSING_CONTEXT
        else SyntheticFixtureMode.COMPLETE
    )
    fixture = SyntheticTutorContextFixture.select(
        scenario.fixture_id,
        allow_synthetic=True,
        mode=mode,
    )
    controlled = (
        PreInteractionFixture(fixture) if scenario.scenario_id is DemoScenarioId.L0 else fixture
    )
    kwargs: dict[str, object] = {}
    if scenario.scenario_id is DemoScenarioId.L6_BLOCKED:
        kwargs["include_curriculum"] = False
    elif scenario.scenario_id is DemoScenarioId.VERIFICATION_FAILED:
        kwargs["llm_provider"] = _SequenceLlm(["The answer is 999."])
    elif scenario.scenario_id is DemoScenarioId.VERIFICATION_INDETERMINATE:
        indeterminate = SemanticVerificationResult(
            assistance_level_compliance=VerificationCheckOutcome.INDETERMINATE,
            answer_leakage=VerificationCheckOutcome.INDETERMINATE,
            factual_support=VerificationCheckOutcome.INDETERMINATE,
            language_appropriateness=VerificationCheckOutcome.INDETERMINATE,
            age_appropriateness=VerificationCheckOutcome.INDETERMINATE,
        )
        kwargs["semantic_verifier"] = DeterministicFakeSemanticVerifier(indeterminate)
    elif scenario.scenario_id is DemoScenarioId.PROVIDER_FAILURE:
        kwargs["llm_provider"] = _SequenceLlm([LlmProviderUnavailableError("controlled failure")])
    orchestrator = build_controlled_tutor_orchestrator(controlled, **kwargs)  # type: ignore[arg-type]
    message = (
        "Can you help me?"
        if scenario.scenario_id is DemoScenarioId.MAPPER_ABSTENTION
        else student_message
    )
    return orchestrator.run(
        TutorWorkflowRequest(
            learner_id=fixture.learner_id,
            student_message=message,
            response_language=response_language,
        )
    )


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def demo_access_allowed(configured_key: str, supplied_key: str | None) -> bool:
    return bool(configured_key and supplied_key) and hmac.compare_digest(
        configured_key, supplied_key
    )
