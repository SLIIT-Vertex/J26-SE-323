"""Evaluation protocol, assignment, and synthetic analysis. No pilot result is claimed."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.gamification.application.errors import PlayError
from app.gamification.application.evaluation_protocol import (
    load_frozen_protocol,
    protocol_digest,
)
from app.gamification.application.experiment_assignment import (
    AssignExperimentArm,
    AssignmentBook,
    allocate_arm,
)
from app.gamification.domain.types import DecisionMode
from app.gamification.modeling.support_selection.evaluation import (
    SelectionObservation,
    selection_quality,
)

ROOT = Path(__file__).resolve().parents[3]
AT = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def _script(name: str):
    path = ROOT / "tools" / "gamification" / "evaluation" / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_protocol_hash_is_stable_and_a_change_is_refused() -> None:
    protocol = load_frozen_protocol()
    assert protocol.digest == protocol_digest(protocol.document)
    altered = dict(protocol.document)
    altered["sample_size"] = "invented"
    with pytest.raises(PlayError) as caught:
        protocol.require_hash(protocol_digest(altered))
    assert caught.value.code == "PROTOCOL_HASH_MISMATCH"


def test_assignment_is_stable_and_locks_after_an_outcome() -> None:
    protocol = load_frozen_protocol()
    book = AssignmentBook()
    assigner = AssignExperimentArm(protocol=protocol, book=book)
    learner = UUID("00000000-0000-4000-8000-000000000301")
    experiment = uuid4()
    arms = ("baseline_performance_triggered", "proposed_misconception_ig_policy")
    first = assigner.execute(
        experiment_id=experiment,
        learner_id=learner,
        seed=4,
        protocol_hash=protocol.digest,
        at=AT,
    )
    again = assigner.execute(
        experiment_id=experiment,
        learner_id=learner,
        seed=4,
        protocol_hash=protocol.digest,
        at=AT,
    )
    assert again.arm_key == first.arm_key
    assert again.decision_mode is DecisionMode(first.decision_mode)
    book.note_outcome(experiment, learner)
    other_seed = next(
        seed for seed in range(30) if allocate_arm(learner, seed, arms) != first.arm_key
    )
    with pytest.raises(PlayError) as caught:
        assigner.execute(
            experiment_id=experiment,
            learner_id=learner,
            seed=other_seed,
            protocol_hash=protocol.digest,
            at=AT,
        )
    assert caught.value.code == "ASSIGNMENT_LOCKED"


def test_selection_quality_is_cohort_agreement() -> None:
    rows = [
        SelectionObservation("cohort", "visual", predicted_reward=0.2, observed_reward=0.1),
        SelectionObservation("cohort", "steps", predicted_reward=0.8, observed_reward=0.9),
        SelectionObservation("other", "visual", predicted_reward=0.9, observed_reward=0.1),
        SelectionObservation("other", "steps", predicted_reward=0.1, observed_reward=0.8),
    ]
    assert selection_quality(rows) == 0.5


def test_synthetic_comparison_covers_both_arms_and_the_ablation() -> None:
    report = _script("simulate_policy_comparison.py").build_report(seeds=30)
    assert report["provenance"] == "synthetic"
    assert str(report["header"]).startswith("SYNTHETIC")
    assert report["seeds"] >= 30
    arms = report["arms"]
    assert "baseline_performance_triggered" in arms
    assert "proposed_misconception_ig_policy" in arms
    assert report["ablation_without_belief_context"]["simulator_policy"] == "LinUCB_belief_ablated"
    assert "m1" in report["per_misconception_mean_ig"]["LinUCB"]
    analysis = _script("analyze_pilot_export.py")
    tables = analysis.analyze_export(
        _script("simulate_policy_comparison.py").synthetic_export(report)
    )
    assert tables["provenance"] == "synthetic"
    assert set(tables["ancova"]) == {"intercept", "pre_test", "proposed_arm"}
    assert "ci95_low" in tables["independence_gain_ci"]
    assert tables["mixed_effects"]["status"] == "placeholder"
    assert tables["attrition"]
    with pytest.raises(ValueError, match="provenance"):
        analysis.analyze_export({"rows": [{"arm": "baseline_performance_triggered"}]})
