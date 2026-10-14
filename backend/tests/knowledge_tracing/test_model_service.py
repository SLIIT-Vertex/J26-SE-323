"""The knowledge model service.

The golden test is the most important one: it proves the backend reproduces the numbers the
training notebook produced, so there is no training/serving mismatch. If it fails, stop and fix
it before building anything on top (usual causes: wrong skill order, model not in eval mode,
wrong difficulty scale, missing query step).
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import torch

from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import FeatureSpec, load_feature_spec
from app.knowledge_tracing.infrastructure.ml.features import build_arrays
from app.knowledge_tracing.infrastructure.ml.model import MindBridgeDKT
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel

BACKEND = Path(__file__).parents[2]
WEIGHTS = (
    BACKEND / "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
)
GOLDEN = BACKEND / "tests/knowledge_tracing/fixtures/golden_history.json"
SPEC_PATH = BACKEND.parent / "shared" / "feature_spec.json"
WHEN = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def spec() -> FeatureSpec:
    return load_feature_spec(str(SPEC_PATH))


@pytest.fixture(scope="module")
def random_model(spec: FeatureSpec) -> KnowledgeModel:
    """A deterministic untrained network: enough to test plumbing without the weights file."""
    torch.manual_seed(0)
    return KnowledgeModel(MindBridgeDKT(num_skills=len(spec.skills)), spec, "test")


def item(
    index: int, correct: bool = True, source: int = 1, penalty: float = 0.1, n: int = 0
) -> HistoryItem:
    return HistoryItem(
        attempt_id=n,
        question_id="q",
        language="si",
        skill_code=f"S{index}",
        skill_index=index,
        difficulty="medium",
        correct=correct,
        source=source,
        penalty=penalty,
        answered_at=WHEN,
    )


# --- golden test (needs the trained weights) ---------------------------------------------------


def _weights_or_skip() -> None:
    if WEIGHTS.is_file() and GOLDEN.is_file():
        return
    message = f"trained weights or golden fixture missing: {WEIGHTS.name}, {GOLDEN.name}"
    if os.environ.get("CI"):
        pytest.fail(message)  # CI must never silently skip the most important test
    pytest.skip(message)


def golden_students() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.is_file() else []


def to_history(student: dict) -> list[HistoryItem]:
    return [
        item(skill, bool(correct), int(source), penalty, n)
        for n, (skill, correct, source, penalty) in enumerate(
            zip(
                student["skills"],
                student["corrects"],
                student["sources"],
                student["penalties"],
                strict=True,
            )
        )
    ]


@pytest.mark.parametrize("student_number", [0, 1, 2])
def test_matches_the_training_notebook(spec: FeatureSpec, student_number: int) -> None:
    _weights_or_skip()
    student = golden_students()[student_number]
    model = KnowledgeModel.load(WEIGHTS, spec)

    result = {m.code: m.mastery for m in model.mastery(to_history(student))}

    assert list(result) == list(student["expected"]), "skill order differs from the notebook"
    for code, expected in student["expected"].items():
        got = result[code]
        assert (expected is None) == (got is None), f"{code}: unknown/known mismatch"
        if expected is not None:
            assert abs(expected - got) < 1.5e-3, f"{code}: notebook {expected}, backend {got}"


def test_the_golden_file_covers_known_and_unknown_skills() -> None:
    _weights_or_skip()
    expected = [v for s in golden_students() for v in s["expected"].values()]

    assert any(v is None for v in expected)
    assert any(v is not None for v in expected)


def test_weights_load_into_the_documented_architecture(spec: FeatureSpec) -> None:
    _weights_or_skip()

    model = KnowledgeModel.load(WEIGHTS, spec)

    assert model.version.startswith("dkt-v2.1-")
    assert len(model.version.split("-")[-1]) == 8
    assert sum(p.numel() for p in model.model.parameters()) == 103_585
    assert not model.model.training


def test_the_same_weights_always_give_the_same_version(spec: FeatureSpec) -> None:
    _weights_or_skip()

    assert KnowledgeModel.load(WEIGHTS, spec).version == KnowledgeModel.load(WEIGHTS, spec).version


def test_weights_for_a_different_architecture_are_refused(
    spec: FeatureSpec, tmp_path: Path
) -> None:
    wrong = MindBridgeDKT(num_skills=len(spec.skills), hidden=64)
    path = tmp_path / "wrong.pt"
    torch.save(wrong.state_dict(), path)

    with pytest.raises(RuntimeError):
        KnowledgeModel.load(path, spec)


# --- behaviour that needs no weights ----------------------------------------------------------


def test_an_empty_history_is_all_unknown(random_model: KnowledgeModel) -> None:
    result = random_model.mastery([])

    assert len(result) == 30
    assert all(m.mastery is None and m.attempts == 0 for m in result)
    assert random_model.item_probabilities([]) is None


def test_results_are_in_spec_order(random_model: KnowledgeModel, spec: FeatureSpec) -> None:
    result = random_model.mastery([item(0)])

    assert [m.code for m in result] == list(spec.skills)
    assert [m.index for m in result] == list(range(30))


def test_a_skill_needs_three_attempts_to_be_known(random_model: KnowledgeModel) -> None:
    history = [item(5, n=0), item(5, n=1), item(7, n=2), item(5, n=3), item(7, n=4)]

    result = {m.index: m for m in random_model.mastery(history)}

    assert result[5].attempts == 3 and result[5].mastery is not None
    assert result[7].attempts == 2 and result[7].mastery is None  # known to be seen, still unknown
    assert result[0].attempts == 0 and result[0].mastery is None


def test_known_mastery_is_a_probability_rounded_to_three_places(
    random_model: KnowledgeModel,
) -> None:
    history = [item(2, correct=bool(n % 2), n=n) for n in range(10)]

    value = next(m.mastery for m in random_model.mastery(history) if m.index == 2)

    assert value is not None
    assert 0.0 < value < 1.0
    assert value == round(value, 3)


def test_inference_is_deterministic(random_model: KnowledgeModel) -> None:
    history = [item(n % 4, n % 3 != 0, n % 2, 0.05 * (n % 5), n) for n in range(20)]

    assert random_model.mastery(history) == random_model.mastery(history)


def test_item_probabilities_have_one_row_per_skill_and_three_levels(
    random_model: KnowledgeModel,
) -> None:
    history = [item(n % 3, n % 2 == 0, n % 2, 0.1, n) for n in range(12)]

    probabilities = random_model.item_probabilities(history)

    assert probabilities is not None
    assert probabilities.shape == (30, 3)
    assert np.all((probabilities > 0) & (probabilities < 1))


def test_the_medium_column_equals_the_mastery_values(random_model: KnowledgeModel) -> None:
    history = [item(n % 3, n % 2 == 0, n % 2, 0.1, n) for n in range(15)]

    probabilities = random_model.item_probabilities(history)
    assert probabilities is not None
    for entry in random_model.mastery(history):
        if entry.mastery is not None:
            assert entry.mastery == pytest.approx(float(probabilities[entry.index, 1]), abs=5e-4)


def test_only_the_last_140_attempts_are_used(random_model: KnowledgeModel) -> None:
    long_history = [item(n % 5, n % 3 != 0, n % 2, 0.1, n) for n in range(300)]

    assert build_arrays(long_history, 140).skills == [it.skill_index for it in long_history[-140:]]
    assert random_model.mastery(long_history) == random_model.mastery(long_history[-140:])


def test_source_changes_the_prediction(spec: FeatureSpec) -> None:
    """The research contribution: digital and paper answers are not treated the same."""
    _weights_or_skip()
    model = KnowledgeModel.load(WEIGHTS, spec)
    digital = [item(3, n % 2 == 0, 1, 0.1, n) for n in range(30)]
    paper = [item(3, n % 2 == 0, 0, 0.08, n) for n in range(30)]

    digital_value = next(m.mastery for m in model.mastery(digital) if m.index == 3)
    paper_value = next(m.mastery for m in model.mastery(paper) if m.index == 3)

    assert digital_value != paper_value


def test_build_arrays_maps_each_field() -> None:
    history = [item(4, True, 1, 0.25, 0), item(9, False, 0, 0.08, 1)]

    arrays = build_arrays(history, 140)

    assert arrays.skills == [4, 9]
    assert arrays.corrects == [1.0, 0.0]
    assert arrays.sources == [1.0, 0.0]
    assert arrays.penalties == [0.25, 0.08]
    assert len(arrays) == 2
