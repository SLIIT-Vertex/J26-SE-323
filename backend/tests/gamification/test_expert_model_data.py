"""The expert model data is complete and holds exactly what the rule-based models do today.

Every check reads the package and the frozen rule-based reference fixtures. Only the last test
looks at the rules themselves, to confirm the detection thresholds were copied correctly.
"""

import hashlib
import importlib.util
import json
from collections import Counter
from itertools import pairwise
from pathlib import Path

import pytest

from app.gamification.application.learning_flow_orchestration import GAME_FLOW_TYPES

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools" / "gamification" / "datasets" / "build_expert_model_data.py"
PACKAGE = ROOT / "data" / "gamification" / "expert-model-data" / "v1"
FIXTURES = Path(__file__).parent / "fixtures"
UNKNOWN = "unknown_or_other"
LABELS_NEEDING_REVIEW = {
    "MAT": {"invalid_scene_evidence"},
    "SIN": {
        "clue_combination_failure",
        "exclamation_context_missed",
        "familiar_answer_recall_without_checking",
        "figurative_taken_literally",
        "reporting_clause_inclusion",
        "single_clue_contradiction_ignored",
        "vocabulary_or_referent_unfamiliarity",
    },
    "ENG": set(),
}


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(TOOL.stem, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def beliefs():
    return _json(FIXTURES / "rule_based_beliefs.json")


@pytest.fixture(scope="module")
def orders():
    return _json(FIXTURES / "rule_based_support_orders.json")


@pytest.fixture(scope="module")
def tables():
    return {
        path.stem: _json(path) for path in sorted((PACKAGE / "misconception_tables").glob("*.json"))
    }


@pytest.fixture(scope="module")
def settings():
    return _json(PACKAGE / "misconception_settings.json")


def _band(tool, table, given) -> str:
    return tool.evidence_band(
        table["evidence_band_rule"], given["response_time_ms"], given["interaction_summary"]
    )


def _rewritten(table, code: str, summary) -> str:
    if code != UNKNOWN or not summary:
        return code
    for rewrite in table["interaction_rewrites"]:
        value = summary.get(rewrite["field"])
        if rewrite["condition"] == "equals" and value is rewrite["value"]:
            return rewrite["error_code"]
        if rewrite["condition"] == "at_least" and type(value) is int and value >= rewrite["value"]:
            return rewrite["error_code"]
    return code


def test_package_regenerates_identically(tool) -> None:
    files = tool.build_package()
    for path, text in files.items():
        assert (PACKAGE / path).read_text(encoding="utf-8") == text, path
    manifest = _json(PACKAGE / "manifest.json")
    assert manifest == tool.build_manifest(files)
    assert manifest["files"] == {
        path: hashlib.sha256(text.encode("utf-8")).hexdigest() for path, text in files.items()
    }
    assert manifest["evidence_status"] == "provisional_expert_assumption"
    assert manifest["reviewed_by"] is None
    assert manifest["reference_fixtures"] == {
        name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        for name in ("rule_based_beliefs.json", "rule_based_support_orders.json")
    }


def test_every_game_has_a_complete_misconception_table(tables, settings) -> None:
    assert list(tables) == sorted(flow_type.area_id for flow_type in GAME_FLOW_TYPES)
    bands = set(settings["bands"])
    assert set(settings["uncertain_bands"]) < bands
    for area_id, table in tables.items():
        codes = table["codes"]
        assert UNKNOWN in codes, area_id
        assert set(table["class_priors"]) == set(codes)
        assert all(value > 0 for value in table["class_priors"].values())
        assert table["evidence_bands"][0] == "normal"
        assert set(table["evidence_bands"]) <= bands
        assert set(table["error_likelihoods"]) == set(table["evidence_bands"])
        for band, rows in table["error_likelihoods"].items():
            assert set(rows) == {*codes, "__unseen__"}, (area_id, band)
            for row in rows.values():
                assert set(row) == set(codes)
                assert all(value > 0 for value in row.values())
                assert sum(row.values()) == pytest.approx(1)


def test_tables_hold_every_frozen_belief(tool, tables, beliefs) -> None:
    areas = {area["area_id"]: area for area in beliefs["areas"]}
    checked = Counter()
    for record in beliefs["game_belief"]:
        table = tables[record["area_id"]]
        given = areas[record["area_id"]]["inputs"][record["input"]]
        code = _rewritten(table, record["error_code"], given["interaction_summary"])
        row = table["error_likelihoods"][_band(tool, table, given)].get(code)
        row = row or table["error_likelihoods"][_band(tool, table, given)]["__unseen__"]
        assert [row[c] for c in table["codes"]] == record["belief"]["likelihood"], record
        checked[table["subject"]] += 1
    assert set(checked) == {"MAT", "ENG", "SIN"}


def test_learner_prior_settings_reproduce_every_frozen_prior(tables, settings, beliefs) -> None:
    pseudocount = settings["learner_prior"]["pseudocount"]
    for record in beliefs["learner_prior"]:
        table = tables[record["area_id"]]
        codes = table["codes"]
        counts = Counter(record["prior_window"])
        weights = [
            value * (pseudocount + counts[code])
            for code, value in zip(codes, record["belief"]["likelihood"], strict=True)
        ]
        total = sum(weights)
        assert [w / total for w in weights] == pytest.approx(
            record["belief"]["probabilities"], abs=1e-12
        )


def test_uncertainty_rule_reproduces_every_frozen_reading(tool, tables, settings, beliefs) -> None:
    rule = settings["uncertainty_rule"]
    areas = {area["area_id"]: area for area in beliefs["areas"]}
    for record in beliefs["game_belief"] + beliefs["learner_prior"]:
        table = tables[record["area_id"]]
        given = areas[record["area_id"]]["inputs"][record["input"]]
        probabilities = record["belief"]["probabilities"]
        likelihood = record["belief"]["likelihood"]
        ordered = sorted(probabilities, reverse=True)
        # The answer's own evidence, before the learner prior, decides the unknown-top cause.
        evidence_top = table["codes"][likelihood.index(max(likelihood))]
        uncertain = (
            ordered[0] < rule["top_probability_below"]
            or ordered[0] - ordered[1] < rule["top_two_margin_below"]
            or _band(tool, table, given) in settings["uncertain_bands"]
            or (table["unknown_top_is_uncertain"] and evidence_top == rule["unknown_code"])
        )
        assert uncertain is record["model1_uncertain"], record


def test_unknown_top_setting_is_on_for_the_games_that_read_it(tables) -> None:
    assert {table["game"] for table in tables.values() if table["unknown_top_is_uncertain"]} == {
        "NumberWorldFlow",
        "AdditionAdventureFlow",
        "NumberPatternsFlow",
        "SubtractionAdventureFlow",
        "MultiplicationAdventureFlow",
        "SinhalaPillamFlow",
        "SinhalaPunctuationFlow",
        "SinhalaRiddleFlow",
    }


def test_every_label_has_a_reason_family(tables) -> None:
    families = _json(PACKAGE / "reason_families.json")
    for subject in ("MAT", "ENG", "SIN"):
        labels = families["subjects"][subject]["labels"]
        codes = {
            code
            for table in tables.values()
            if table["subject"] == subject
            for code in table["codes"]
        }
        assert set(labels) == codes
        assert all(row["reason_family"] in families["reason_families"] for row in labels.values())
        flagged = {label for label, row in labels.items() if row["needs_review"]}
        assert flagged == LABELS_NEEDING_REVIEW[subject]
        assert all(labels[label]["reason_family"] == "unclear" for label in flagged)


def test_expected_gains_cover_every_cell_and_help(orders) -> None:
    gains = _json(PACKAGE / "support_gains.json")
    assert gains["prior_strength"] > 0
    assert 0 < gains["own_success_rate_gain"] <= 1 - gains["first_gain"]
    # Only the Sinhala packages move on from a first help that did not transfer.
    assert gains["previous_first_not_transferred_gain"] == {"MAT": 0.0, "ENG": 0.0, "SIN": -0.45}
    assert gains["tie_tolerance"] > 0
    for cell in gains["cells"]:
        values = [cell["expected_gain"][support] for support in cell["order"]]
        assert values == sorted(values, reverse=True)
        assert min(a - b for a, b in pairwise(values)) > gains["tie_tolerance"]
        assert values[0] - values[-1] < gains["own_success_rate_gain"]
    cells = {
        (c["subject"], c["reason_family"], c["model1_uncertain"], c["learning_state"]): c
        for c in gains["cells"]
    }
    for subject in ("MAT", "ENG", "SIN"):
        helps = set(gains["help_types"][subject])
        for family in ("representation", "procedure", "relation", "prerequisite", "unclear"):
            for state in gains["learning_states"]:
                assert set(cells[(subject, family, False, state)]["expected_gain"]) == helps
        for state in gains["learning_states"]:
            assert set(cells[(subject, "unclear", True, state)]["expected_gain"]) == helps
    assert gains["unused_reference"]["SIN"]["lead_by_reason"] == orders["lead_by_reason"]["SIN"]


def test_sorting_by_expected_gain_reproduces_todays_order(orders) -> None:
    gains = _json(PACKAGE / "support_gains.json")
    families = _json(PACKAGE / "reason_families.json")["subjects"]
    cells = {
        (c["subject"], c["reason_family"], c["model1_uncertain"], c["learning_state"]): c
        for c in gains["cells"]
    }
    checked = Counter()
    for decision in orders["decisions"]:
        if decision["condition"] != "proposed" or decision["history"] != "none":
            continue
        subject = decision["subject"]
        family = (
            "unclear"
            if decision["model1_uncertain"]
            else families[subject]["labels"][decision["model1_label"]]["reason_family"]
        )
        cell = cells[(subject, family, decision["model1_uncertain"], decision["learning_state"])]
        drawable = [s for s in cell["order"] if s in decision["renderable"]]
        order = sorted(drawable, key=lambda s: (-cell["expected_gain"][s], cell["order"].index(s)))
        expected = (
            decision["delivered"]["support_order"]
            if subject == "SIN"
            else decision["decision"]["support_order"]
        )
        assert order == expected, decision
        checked[(subject, decision["helps"])] += 1
    assert {helps for _, helps in checked} == {
        "all_eligible",
        "lead_not_drawable",
        "worked_example_only",
    }


def test_detection_rules_keep_what_the_earlier_rules_did(tool) -> None:
    # The values the deleted rules held at commit 8c0965f: Sinhala motor thresholds and the
    # Subtraction answer rewrites, which now live only in the expert data.
    assert tool.SIGNALS["motor"]["any"] == {"correction_count": 3, "cancelled_drag_count": 2}
    table = _json(PACKAGE / "misconception_tables" / "G5-AREA-MAT-04.json")
    expected = [
        ({"started_from_ones": False, "alignment_valid": False}, "starts_from_left"),
        ({"alignment_valid": False, "invalid_exchange_count": 2}, "misaligns_place_columns"),
        ({"invalid_exchange_count": 0, "operation_changes": 1}, "uses_addition_instead"),
        ({"story_reorder_count": 3}, "smaller_quantity_as_minuend"),
        ({"story_reorder_count": 0}, UNKNOWN),
        ({"first_action_ms": 800}, UNKNOWN),
    ]
    for summary, rewritten in expected:
        assert _rewritten(table, UNKNOWN, summary) == rewritten, summary
        # A named mistake is never rewritten.
        assert _rewritten(table, "starts_from_left", summary) == "starts_from_left"
