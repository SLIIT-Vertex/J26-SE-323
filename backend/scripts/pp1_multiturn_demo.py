"""Reproducible PP1 multi-turn Fractions demonstration through the real research HTTP API.

Pipeline exercised: E5 Skill Mapper -> context assembly (KT, Learner State, assessment ledger,
assistance history) -> Controller V1 -> experimental Gemini draft (unverified) -> researcher-reviewed
attempt -> next decision. Only the Gemini client is swapped in rehearsal mode.

Modes:
  --provider fake    (default) canned drafts, no network. A rehearsal, not evidence of Gemini output.
  --provider gemini  real Gemini via the configured research settings. Requires
                     PP1_LIVE_GEMINI_APPROVED=true and is capped by --max-gemini-calls.
  --database sqlite      (default) fresh in-memory database with a synthetic demo learner.
  --database configured  DATABASE_URL from backend/.env; requires --learner-id.

Output: sanitized JSON and Markdown transcripts in research/adaptive-tutor/pp1-demo/. No API key,
session token, or learner identifier is written. Drafts keep the EXPERIMENTAL notice.
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.api.router import get_research_tutor_service
from app.adaptive_tutor.application.generation import GenerationPrompt
from app.adaptive_tutor.application.verification import (
    VerificationRequest,
    verify_response,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure.gemini import (
    GeminiGenerationConfig,
    _create_google_genai_client,
)
from app.adaptive_tutor.infrastructure.local_research import (
    build_local_research_tutor_service,
    validate_local_research_settings,
)
from app.adaptive_tutor.infrastructure.research_sessions import REHEARSAL_PROVIDER_NAME
from app.adaptive_tutor.infrastructure.tutor_history import (
    TutorInteractionEventModel,
)
from app.config import Settings
from app.main import app
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPOSITORY_ROOT / "research/adaptive-tutor/pp1-demo"
API = "/api/v1/adaptive-tutor/research"
SYNTHETIC_DEMO_LEARNER = UUID("00000000-0000-4000-8000-000000000101")

SCENARIO_ID = "pp1-fractions-escalation-fading-v1"
QUESTION = "Why is 1/2 equal to 2/4?"
LANGUAGE = "en"
# (label, is_correct, severity, level expected under the PP1 cold-start defaults mastery=0, support=0)
ATTEMPTS = (
    ("a1", False, 0.7, "L2"),
    ("a2", False, 0.7, "L2"),
    ("a3", False, 0.7, "L3"),
    ("a4", False, 0.7, "L4"),
    ("a5", False, 0.3, "L3"),
    ("a6", True, 0.0, "L0"),
)
QUESTION_EXPECTED_LEVEL = "L0"
# Attempts come from this script, not from a student or a human review of student work.
SCRIPTED_SCORING_VERSION = "scripted-scenario-v1"
ATTEMPT_SOURCE = "SCRIPTED_SCENARIO: predetermined outcomes, not observed or reviewed student work"
# Provider failures that end a live run immediately; a second timeout also ends it.
FATAL_PROVIDER_REASONS = frozenset(
    {
        "AUTHENTICATION_FAILED",
        "MODEL_NOT_FOUND",
        "PROVIDER_NOT_CONFIGURED",
        "PROVIDER_SDK_NOT_INSTALLED",
    }
)


@dataclass
class CallLog:
    calls: list[dict[str, Any]] = field(default_factory=list)


class FakeRehearsalProvider:
    """A separate provider for offline rehearsals; its drafts can never be labelled as Gemini."""

    name = REHEARSAL_PROVIDER_NAME

    def __init__(self, log: CallLog) -> None:
        self._log = log

    def generate(self, prompt: GenerationPrompt) -> str:
        self._log.calls.append({"seconds": 0.0, "outcome": "OK"})
        return f"[FAKE PROVIDER — NOT GEMINI] Rehearsal draft for {prompt.assistance_level.value}."


class CappedGeminiModels:
    """Real google-genai models wrapper: counts, times, and hard-limits generation calls.

    Holds the Client itself: google-genai closes its HTTP client when the Client object is
    garbage-collected, so keeping only ``client.models`` makes every request fail locally.
    """

    def __init__(self, client: Any, log: CallLog, limit: int) -> None:
        self._client = client
        self._inner = client.models
        self._log = log
        self._limit = limit

    def generate_content(self, **kwargs: Any) -> Any:
        if len(self._log.calls) >= self._limit:
            raise RuntimeError("PP1 demonstration Gemini call limit reached")
        started = time.perf_counter()
        try:
            response = self._inner.generate_content(**kwargs)
        except Exception as error:
            self._log.calls.append(
                {"seconds": time.perf_counter() - started, "outcome": type(error).__name__}
            )
            raise
        self._log.calls.append({"seconds": time.perf_counter() - started, "outcome": "OK"})
        return response


def provider_overrides(
    provider: str, settings: Settings, log: CallLog, limit: int
) -> dict[str, Any]:
    """Composition keyword: a distinct fake provider, or the capped real Gemini client."""

    if provider == "fake":
        return {"llm_provider": FakeRehearsalProvider(log)}
    return {"gemini_client": build_client(settings, log, limit)}


def build_client(settings: Settings, log: CallLog, limit: int) -> Any:
    if os.environ.get("PP1_LIVE_GEMINI_APPROVED", "").casefold() != "true":
        raise PermissionError("set PP1_LIVE_GEMINI_APPROVED=true to permit live Gemini calls")
    real = _create_google_genai_client(GeminiGenerationConfig.from_settings(settings))
    return SimpleNamespace(models=CappedGeminiModels(real, log, limit))


def open_database(mode: str, learner_id: UUID | None) -> tuple[Session, UUID]:
    if mode == "sqlite":
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add(LearnerModel(id=SYNTHETIC_DEMO_LEARNER, grade=5, preferred_language="en"))
        session.commit()
        return session, SYNTHETIC_DEMO_LEARNER
    if learner_id is None:
        raise ValueError("--learner-id is required with --database configured")
    from app.shared.database.session import SessionLocal

    return SessionLocal(), learner_id


def level_checks(level: str | None, text: str | None) -> dict[str, str] | None:
    """Deterministic structural checks only. Diagnostic; never authorization."""

    if level is None or not text:
        return None
    result = verify_response(
        VerificationRequest(
            student_question=QUESTION,
            assistance_level=AssistanceLevel(level),
            response_text=text,
            response_language=LANGUAGE,
            grade=5,
            skill_id="MAT-FRC",
        )
    )
    keep = {
        "RESPONSE_STRUCTURE",
        "LEVEL_STRUCTURE",
        "ANSWER_LEAKAGE",
        "LANGUAGE_SCRIPT",
        "CHILD_SAFETY",
    }
    return {
        check.check.value: f"{check.outcome.value} ({', '.join(code.value for code in check.reason_codes)})"
        for check in result.checks
        if check.check.value in keep
    }


def step_record(
    label: str, body: dict[str, Any], seconds: float, calls_before: int, log: CallLog
) -> dict[str, Any]:
    new_calls = log.calls[calls_before:]
    return {
        "step": label,
        "http_seconds": round(seconds, 3),
        "provider_calls": [
            {"seconds": round(call["seconds"], 3), "outcome": call["outcome"]} for call in new_calls
        ],
        "status": body.get("status"),
        "skill": body.get("confirmed_skill_id"),
        "skill_mapping_status": body.get("skill_mapping_status"),
        "assistance_level": body.get("assistance_level"),
        "controller_reason_codes": body.get("controller_reason_codes"),
        "delivery_authorized": body.get("delivery_authorized"),
        "response_text": body.get("response_text"),
        "experimental_generation_status": body.get("experimental_generation_status"),
        "experimental_provider_name": body.get("experimental_provider_name"),
        "experimental_provider_reason_code": body.get("experimental_provider_reason_code"),
        "experimental_notice": body.get("experimental_notice"),
        "experimental_response_text": body.get("experimental_response_text"),
        "context_provenance": [
            f"{item['input']}: {item['origin']}/{item['status']} ({item['source_id']})"
            for item in body.get("context_provenance", [])
        ],
        "execution_origin": body.get("execution_origin"),
        "deterministic_level_checks": level_checks(
            body.get("assistance_level"), body.get("experimental_response_text")
        ),
    }


# Temporary unavailability (HTTP 502/503), rate limiting and timeouts; any two in a row end a run.
TEMPORARY_PROVIDER_REASONS = frozenset(
    {"PROVIDER_TEMPORARILY_UNAVAILABLE", "RATE_LIMITED", "NETWORK_OR_TIMEOUT"}
)


@dataclass
class RunGuard:
    """Live-run stop rules, evaluated after every step that asked the provider for a draft."""

    consecutive_unavailable: int = 0
    timeouts: int = 0

    def observe(self, step: dict[str, Any], *, first: bool) -> str | None:
        if step["experimental_generation_status"] == "GENERATED":
            self.consecutive_unavailable = 0
            return None
        reason = step["experimental_provider_reason_code"] or step["experimental_generation_status"]
        if first:
            return f"first Gemini call did not generate a draft ({reason})"
        if reason in FATAL_PROVIDER_REASONS:
            return f"fatal provider failure ({reason})"
        if reason not in TEMPORARY_PROVIDER_REASONS:
            self.consecutive_unavailable = 0
            return None
        self.consecutive_unavailable += 1
        if self.consecutive_unavailable >= 2:
            return "two consecutive temporary provider unavailability errors or timeouts"
        if reason == "NETWORK_OR_TIMEOUT":
            self.timeouts += 1
            if self.timeouts >= 2:
                return "repeated timeouts"
        return None


@dataclass
class Execution:
    steps: list[dict[str, Any]]
    events: list[dict[str, Any]]
    stopped: str | None


def execute(
    http: TestClient,
    db: Session,
    log: CallLog,
    *,
    learner_id: UUID,
    severity_policy: str,
    call_limit: int | None,
) -> Execution:
    """Run the scenario through the research HTTP API; ``http`` must carry the research key."""

    guard = RunGuard()
    steps: list[dict[str, Any]] = []
    stopped: str | None = None
    http.get(f"{API}/status").raise_for_status()
    started = http.post(f"{API}/sessions", json={"learner_id": str(learner_id)})
    started.raise_for_status()
    session_id = started.json()["session_id"]
    headers = {"X-Tutor-Research-Session": started.json()["session_token"]}

    before, clock = len(log.calls), time.perf_counter()
    asked = http.post(
        f"{API}/sessions/{session_id}/questions",
        json={"student_message": QUESTION, "response_language": LANGUAGE},
        headers=headers,
    )
    asked.raise_for_status()
    body = asked.json()
    steps.append(
        {
            **step_record("question", body, time.perf_counter() - clock, before, log),
            "expected_level": QUESTION_EXPECTED_LEVEL,
        }
    )
    interaction_id = body["interaction_id"]
    stopped = guard.observe(steps[-1], first=True)

    for label, correct, severity, expected in ATTEMPTS:
        if stopped is not None:
            break
        if call_limit is not None and len(log.calls) >= call_limit:
            stopped = f"provider call limit reached ({call_limit})"
            break
        before, clock = len(log.calls), time.perf_counter()
        response = http.post(
            f"{API}/sessions/{session_id}/interactions/{interaction_id}/attempts",
            json={
                "idempotency_key": f"{SCENARIO_ID}:{label}",
                "is_correct": correct,
                "partial_credit": None,
                # Scripted outcomes: labelled so they are never mistaken for reviewed student work.
                "severity_category": "CORRECT" if correct else "SCRIPTED_SCENARIO_ERROR",
                "severity_value": severity,
                "severity_policy_version": severity_policy,
                "scoring_version": SCRIPTED_SCORING_VERSION,
                "item_rubric_version": "pp1-scenario-v1",
                "reviewer_confirmed": True,
            },
            headers=headers,
        )
        response.raise_for_status()
        steps.append(
            {
                **step_record(label, response.json(), time.perf_counter() - clock, before, log),
                "annotation": {"is_correct": correct, "severity": severity},
                "expected_level": expected,
            }
        )
        stopped = guard.observe(steps[-1], first=False)

    events = [
        {
            "interaction_sequence": row.interaction_sequence,
            "event_sequence": row.event_sequence,
            "event_type": row.event_type,
            "status": row.status,
            "assistance_level": row.assistance_level,
            "provenance": row.provenance,
        }
        for row in db.scalars(
            select(TutorInteractionEventModel)
            .where(TutorInteractionEventModel.session_id == UUID(session_id))
            .order_by(
                TutorInteractionEventModel.interaction_sequence,
                TutorInteractionEventModel.event_sequence,
            )
        ).all()
    ]
    http.delete(f"{API}/sessions/{session_id}", headers=headers)
    _mark_presentations(steps, events)
    return Execution(steps=steps, events=events, stopped=stopped)


def _mark_presentations(steps: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    """Pair each step's decision with any RESEARCH_PRESENTATION recorded before the next one."""

    presented: list[bool] = []
    for event in events:
        if event["event_type"] == "ASSISTANCE_SELECTED":
            presented.append(False)
        elif event["event_type"] == "RESEARCH_PRESENTATION" and presented:
            presented[-1] = True
    for step, shown in zip(steps, presented, strict=False):
        step["draft_presented"] = shown


def build_report(
    execution: Execution,
    log: CallLog,
    *,
    provider: str,
    provider_label: str,
    thinking_level: str,
    database: str,
    call_limit: int | None,
) -> dict[str, Any]:
    steps, events, stopped = execution.steps, execution.events, execution.stopped
    types = [event["event_type"] for event in events]
    invariants = {
        "no_learner_delivery_events": not {"RESPONSE_DELIVERED", "DELIVERY_AUTHORIZED"}
        & set(types),
        "no_verified_response_text": all(step["response_text"] is None for step in steps),
        "no_delivery_authorized": all(step["delivery_authorized"] is False for step in steps),
        "presentation_only_for_generated_drafts": all(
            step.get("draft_presented") == (step["experimental_generation_status"] == "GENERATED")
            for step in steps
        ),
        "levels_match_full_presentation_plan": all(
            step["assistance_level"] == step["expected_level"] for step in steps
        ),
        "scenario_completed": stopped is None and len(steps) == len(ATTEMPTS) + 1,
    }
    return {
        "scenario_id": SCENARIO_ID,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider,
        "provider_label": provider_label,
        "gemini_thinking_level": thinking_level or "(provider default)",
        "database": database,
        "learner": (
            "synthetic demo learner" if database == "sqlite" else "configured learner (id withheld)"
        ),
        "question": QUESTION,
        "language": LANGUAGE,
        "notice": "EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS",
        "attempt_source": ATTEMPT_SOURCE,
        "plan_note": (
            "Expected levels assume every draft is generated and shown; a failed draft is not "
            "previous assistance, so later levels legitimately differ."
        ),
        "provider_call_count": len(log.calls),
        "provider_call_limit": call_limit,
        "stopped_early": stopped,
        "steps": steps,
        "history_events": events,
        "invariants": invariants,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    settings = Settings()
    policies = sorted(validate_local_research_settings(settings))
    if not settings.tutor_pp1_experimental_demo_enabled:
        raise ValueError("TUTOR_PP1_EXPERIMENTAL_DEMO_ENABLED must be true for this demonstration")
    log = CallLog()
    call_limit = args.max_gemini_calls if args.provider == "gemini" else None
    overrides = provider_overrides(args.provider, settings, log, args.max_gemini_calls)
    session, learner_id = open_database(args.database, args.learner_id)
    service = build_local_research_tutor_service(settings, session, **overrides)
    app.dependency_overrides[get_research_tutor_service] = lambda: service
    http = TestClient(app, headers={"X-Tutor-Research-Key": settings.tutor_research_access_key})
    try:
        execution = execute(
            http,
            session,
            log,
            learner_id=learner_id,
            severity_policy=policies[0],
            call_limit=call_limit,
        )
    finally:
        app.dependency_overrides.pop(get_research_tutor_service, None)
        session.close()
    return build_report(
        execution,
        log,
        provider=args.provider,
        provider_label=(
            "FAKE PROVIDER REHEARSAL — not Gemini output"
            if args.provider == "fake"
            else f"google-gemini {settings.tutor_gemini_model}"
        ),
        thinking_level=settings.tutor_gemini_thinking_level,
        database=args.database,
        call_limit=call_limit,
    )


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# PP1 multi-turn demonstration — {report['scenario_id']}",
        "",
        (
            f"- Run: {report['run_at']} · Provider: **{report['provider_label']}** · "
            f"Thinking: {report['gemini_thinking_level']} · Database: {report['database']} "
            f"({report['learner']})"
        ),
        f"- Question ({report['language']}): “{report['question']}”",
        f"- All drafts: **{report['notice']}**. No draft was verified or delivered to a learner.",
        (
            f"- Provider calls: {report['provider_call_count']}"
            f" (limit {report['provider_call_limit'] or 'n/a'})"
        ),
        f"- Stopped early: {report['stopped_early'] or 'no'}",
        "",
        f"- Attempts: {report['attempt_source']}",
        f"- {report['plan_note']}",
        "",
        "| Step | Annotation | Level (plan) | Controller reasons | Draft status | Shown | Provider s |",
        "|---|---|---|---|---|---|---|",
    ]
    for step in report["steps"]:
        annotation = step.get("annotation")
        note = (
            "—"
            if annotation is None
            else (
                "correct"
                if annotation["is_correct"]
                else f"incorrect, severity {annotation['severity']}"
            )
        )
        seconds = ", ".join(str(call["seconds"]) for call in step["provider_calls"]) or "—"
        lines.append(
            f"| {step['step']} | {note} | {step['assistance_level']} ({step['expected_level']}) | "
            f"{', '.join(step['controller_reason_codes'] or [])} | "
            f"{step['experimental_generation_status']}"
            f"{' / ' + step['experimental_provider_reason_code'] if step['experimental_provider_reason_code'] else ''}"
            f" | {'yes' if step.get('draft_presented') else 'no'} | {seconds} |"
        )
    lines += ["", "## Drafts", ""]
    for step in report["steps"]:
        lines.append(f"### {step['step']} — {step['assistance_level']}")
        lines.append("")
        lines.append(f"> {step['experimental_response_text'] or '(no draft)'}")
        lines.append("")
        lines.append(
            f"Deterministic checks (diagnostic only): {step['deterministic_level_checks']}"
        )
        lines.append("")
    lines += ["## Invariants", ""]
    lines += [
        f"- {name}: **{'PASS' if ok else 'FAIL'}**" for name, ok in report["invariants"].items()
    ]
    lines += ["", "## Context provenance (last step)", ""]
    lines += [f"- {item}" for item in report["steps"][-1]["context_provenance"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=("fake", "gemini"), default="fake")
    parser.add_argument("--database", choices=("sqlite", "configured"), default="sqlite")
    parser.add_argument("--learner-id", type=UUID)
    parser.add_argument("--max-gemini-calls", type=int, default=len(ATTEMPTS) + 1)
    args = parser.parse_args()
    report = run(args)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{report['scenario_id']}-{args.provider}-{args.database}-{report['run_at'][:19].replace(':', '')}"
    (OUTPUT_DIR / f"{stem}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / f"{stem}.md").write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps({"output": f"{stem}.{{json,md}}", "invariants": report["invariants"]}, indent=2)
    )
    return 0 if all(report["invariants"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
