"""Checks the real files in backend/data/question_bank (skipped when the folder is absent)."""

from pathlib import Path

import pytest

from app.knowledge_tracing.application.question_import import (
    ImageInfo,
    build_plan,
    load_files,
)

BANK = Path(__file__).parents[2] / "data" / "question_bank"

pytestmark = pytest.mark.skipif(not BANK.is_dir(), reason="question bank folder not present")


class AnyImage:
    def describe(self, language: str, question_id: str) -> ImageInfo:
        return ImageInfo(f"{language}/{question_id}", 800, 400, f"{language}-{question_id}")


def test_the_real_files_are_consistent() -> None:
    plan = build_plan(load_files(BANK), AnyImage())

    assert plan.ok, [str(e) for e in plan.errors]
    assert len(plan.skills) == 30
    assert len(plan.questions) == 328
    assert all(set(q.variants) == {"si", "ta"} for q in plan.questions)
    assert all(len(q.variants["si"].parts) == len(q.variants["ta"].parts) for q in plan.questions)
