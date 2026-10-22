from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adaptive_tutor.infrastructure.local_research import (
    configured_research_trusted_answer,
)
from app.config import Settings
from scripts import check_adaptive_tutor_readiness as readiness
from scripts.import_research_fractions import load_manifest


def test_readiness_reports_blocks_without_printing_secrets(monkeypatch) -> None:
    secret = "must-not-appear"
    monkeypatch.setattr(readiness, "_e5", lambda: "cached test model")
    checks = readiness.run_checks(
        Settings(
            database_url="sqlite://",
            tutor_research_access_key=secret,
            tutor_gemini_api_key=secret,
            tutor_semantic_verifier_api_key=secret,
        ),
        learner_id=None,
        session_id=None,
        language="en",
        max_age_ms=60_000,
        now=datetime(2026, 10, 19, tzinfo=UTC),
    )

    report = "\n".join(f"{item.name}: {item.reason}" for item in checks)
    assert secret not in report
    assert {item.name for item in checks} == {
        "POSTGRESQL",
        "MIGRATIONS",
        "RESEARCH_AUTHORIZATION",
        "E5_MODEL",
        "LEARNER",
        "KT_MASTERY",
        "LEARNER_STATE",
        "CURRICULUM_MAT_FRC",
        "GEMINI",
        "INDEPENDENT_VERIFIER",
        "CONTROLLED_SEVERITY_POLICY",
        "TRUSTED_ANSWER",
        "RESEARCH_COMPOSITION",
    }
    assert not all(item.ready for item in checks)


@pytest.mark.requires_research
def test_unreviewed_fractions_template_is_not_importable() -> None:
    template = (
        Path(__file__).resolve().parents[3]
        / "research/adaptive-tutor/fractions-live-template/manifest.UNREVIEWED.json"
    )

    with pytest.raises(ValueError, match="unreviewed template"):
        load_manifest(template)


def test_trusted_answer_is_exact_question_and_fractions_only() -> None:
    provider = configured_research_trusted_answer(
        Settings(
            tutor_research_trusted_question="What is 1/2 + 1/4?",
            tutor_research_trusted_answers_json='["3/4", "0.75"]',
            tutor_research_trusted_answer_provenance="review:adult-research-v1",
        )
    )

    answer = provider.get_trusted_answer(
        student_question="What is 1/2 + 1/4?",
        skill_id="MAT-FRC",
        grade=5,
    )
    assert answer is not None
    assert answer.accepted_answers == ("3/4", "0.75")
    assert (
        provider.get_trusted_answer(
            student_question="What is 2/3 + 1/3?",
            skill_id="MAT-FRC",
            grade=5,
        )
        is None
    )
