import json
from pathlib import Path

import pytest

from app.knowledge_tracing.domain.feature_spec import load_feature_spec
from app.knowledge_tracing.domain.penalty import (
    DIGITAL,
    DIGITAL_FORMULA,
    PAPER,
    compute_penalty,
)

SPEC_PATH = Path(__file__).parents[3] / "shared" / "feature_spec.json"
PAPER_PENALTY = 0.08


def penalty(time_ms: int | None, hints: int | None) -> float:
    return compute_penalty(DIGITAL, time_ms, hints, PAPER_PENALTY)


def test_no_hints_and_no_time_pressure() -> None:
    assert penalty(0, 0) == 0.0


def test_one_hint_and_fourteen_seconds() -> None:
    assert penalty(14_000, 1) == pytest.approx(0.6 * (1 / 3) + 0.4 * (14_000 / 180_000))


def test_hints_are_capped_at_three() -> None:
    assert penalty(0, 3) == pytest.approx(0.6)
    assert penalty(0, 10) == pytest.approx(0.6)


def test_time_is_capped_at_three_minutes() -> None:
    assert penalty(180_000, 0) == pytest.approx(0.4)
    assert penalty(600_000, 0) == pytest.approx(0.4)


def test_the_worst_digital_answer_has_penalty_one() -> None:
    assert penalty(600_000, 10) == pytest.approx(1.0)


def test_missing_hints_count_as_zero() -> None:
    assert penalty(30_000, None) == pytest.approx(penalty(30_000, 0))


def test_missing_time_uses_twelve_seconds() -> None:
    assert penalty(None, 0) == pytest.approx(0.4 * 12_000 / 180_000)
    assert penalty(None, None) == pytest.approx(penalty(12_000, 0))


def test_paper_answers_get_the_constant_whatever_else_is_sent() -> None:
    assert compute_penalty(PAPER, None, None, PAPER_PENALTY) == PAPER_PENALTY
    assert compute_penalty(PAPER, 999_999, 7, PAPER_PENALTY) == PAPER_PENALTY


@pytest.mark.parametrize("source", [2, -1])
def test_unknown_source_is_rejected(source: int) -> None:
    with pytest.raises(ValueError):
        compute_penalty(source, 1000, 0, PAPER_PENALTY)


def test_negative_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        penalty(-1, 0)
    with pytest.raises(ValueError):
        penalty(0, -1)


def test_the_code_formula_is_the_one_in_the_feature_spec() -> None:
    """Training and serving must agree; if the spec formula changes, this fails."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    assert spec["penalty"]["digital_formula"] == DIGITAL_FORMULA


def test_feature_spec_loader_reads_the_shared_file() -> None:
    spec = load_feature_spec(str(SPEC_PATH))

    assert len(spec.skills) == 30
    assert spec.paper_penalty == 0.08
    assert (spec.digital_source, spec.paper_source) == (1, 0)
    assert spec.history_cap == 140
    assert spec.skill_index("APT-PAT") == 0
    assert spec.skill_index("ENV-CIV") == 29
