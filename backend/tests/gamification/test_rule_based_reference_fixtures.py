"""The rule-based reference fixtures: the frozen record of what the earlier rules returned.

They hold today's equivalence targets for the research models. The rules are gone, so the files
are never rebuilt; these checks keep them complete and unchanged.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from app.gamification.application.learning_flow_orchestration import GAME_FLOW_TYPES
from app.gamification.modeling.support_selection.baseline_order import subject_of

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BELIEFS_FILE = "rule_based_beliefs.json"
ORDERS_FILE = "rule_based_support_orders.json"
MANIFEST_FILE = "rule_based_reference_manifest.json"
SINHALA_CALLS = {
    "motor_corrections",
    "motor_cancelled_drags",
    "rendering_problem",
    "motor_and_rendering",
}


@pytest.fixture(scope="module")
def stored() -> dict[str, str]:
    return {
        name: (FIXTURES / name).read_text(encoding="utf-8") for name in (BELIEFS_FILE, ORDERS_FILE)
    }


@pytest.fixture(scope="module")
def beliefs(stored):
    return json.loads(stored[BELIEFS_FILE])


@pytest.fixture(scope="module")
def orders(stored):
    return json.loads(stored[ORDERS_FILE])


def test_manifest_hashes_the_stored_fixtures(stored) -> None:
    manifest = json.loads((FIXTURES / MANIFEST_FILE).read_text("utf-8"))
    assert manifest["fixtures"] == {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in stored.items()
    }
    # The rule sources they were frozen from, recorded by commit and hash.
    assert manifest["rule_sources"] and manifest["source_commit"]


def test_every_registered_game_is_frozen(beliefs, orders) -> None:
    areas = [area["area_id"] for area in beliefs["areas"]]
    assert areas == [flow_type.area_id for flow_type in GAME_FLOW_TYPES]
    assert Counter(subject_of(area) for area in areas) == {"MAT": 16, "ENG": 18, "SIN": 3}
    assert [
        area
        for subject in ("MAT", "ENG", "SIN")
        for area in orders["eligible_helps"][subject]["games"]
    ] == sorted(areas, key=lambda area: ("MAT", "ENG", "SIN").index(subject_of(area)))


def test_every_listed_code_has_every_call_and_input(beliefs) -> None:
    unlisted = beliefs["unlisted_code"]
    for area in beliefs["areas"]:
        area_id = area["area_id"]
        observed = {*area["codes"], unlisted}
        calls = {"plain", "sparse"} | (SINHALA_CALLS if subject_of(area_id) == "SIN" else set())
        raw = {
            (r["error_code"], r["call"]) for r in beliefs["infer_belief"] if r["area_id"] == area_id
        }
        assert raw == {(code, call) for code in observed for call in calls}
        game = {
            (r["error_code"], r["input"]) for r in beliefs["game_belief"] if r["area_id"] == area_id
        }
        assert {(code, name) for code in observed for name in area["inputs"]} >= game
        assert {code for code, _ in game} == observed
        histories = {r["history"] for r in beliefs["learner_prior"] if r["area_id"] == area_id}
        assert histories == set(area["prior_histories"])


def test_frozen_beliefs_are_complete_distributions(beliefs) -> None:
    lengths = {area["area_id"]: len(area["codes"]) for area in beliefs["areas"]}
    for section in ("infer_belief", "game_belief", "learner_prior"):
        for record in beliefs[section]:
            probabilities = record["belief"]["probabilities"]
            assert len(probabilities) == lengths[record["area_id"]]
            assert sum(probabilities) == pytest.approx(1)


def test_every_label_has_a_family_and_every_decision_is_recorded(beliefs, orders) -> None:
    for subject in ("MAT", "ENG", "SIN"):
        labels = {
            code
            for area in beliefs["areas"]
            if area["subject"] == subject
            for code in area["codes"]
        }
        rows = orders["reason_families"][subject]["labels"]
        assert set(rows) == labels
        for row in rows.values():
            assert row["lead"] == orders["lead_by_reason"][subject][row["reason_family"]]

        decisions = [d for d in orders["decisions"] if d["subject"] == subject]
        grid = Counter(
            (d["model1_label"], d["model1_uncertain"], d["learning_state"], d["history"])
            for d in decisions
            if d["condition"] == "proposed" and d["helps"] == "all_eligible"
        )
        variants = {(label, uncertain) for label, uncertain, _, _ in grid}
        assert {
            orders["reason_families"][subject]["labels"][label]["reason_family"]
            for label, _ in variants
        } == {row["reason_family"] for row in rows.values()}
        assert set(grid.values()) == {1}
        assert len(grid) == (
            len(variants)
            * len(orders["learning_state_readings"])
            * len(orders["histories"][subject])
        )
        assert all(("delivered" in d) == (subject == "SIN") for d in decisions)
