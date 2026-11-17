"""Build the expert model data package from the frozen rule-based reference fixtures.

Everything the rule-based Model 1 and Model 2 know becomes versioned data in
``data/gamification/expert-model-data/v1/``, so the research models can start from it and the
rules can later be deleted without losing knowledge. The package is read from the reference
fixtures only, never by calling the rules:

- ``misconception_tables/<area>.json``: per game area, its codes, a uniform class prior, one
  likelihood row per evidence band and error code (the game's frozen belief before the learner
  prior), its evidence-band rule, any interaction rewrites and whether an ``unknown_or_other`` top
  label counts as uncertain;
- ``misconception_settings.json``: how evidence bands are detected, the uncertainty rule and the
  learner-prior settings shared by every area;
- ``reason_families.json``: each subject's label to reason-family map;
- ``support_gains.json``: per subject, the expected gain of each help type for every reason family,
  Model 1 uncertainty and Learning State reading, set so that sorting by gain reproduces today's
  help order.

Every value is a provisional expert assumption, not learned from children.

    PYTHONPATH=backend python3 tools/gamification/datasets/build_expert_model_data.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIRECTORY = ROOT / "backend" / "tests" / "gamification" / "fixtures"
BELIEFS_FIXTURE = "rule_based_beliefs.json"
ORDERS_FIXTURE = "rule_based_support_orders.json"
OUTPUT_DIRECTORY = ROOT / "data" / "gamification" / "expert-model-data" / "v1"
PACKAGE_VERSION = "expert-model-data-v1"
EVIDENCE_STATUS = "provisional_expert_assumption"

SUBJECTS = ("MAT", "ENG", "SIN")
REASON_FAMILIES = ("representation", "procedure", "relation", "prerequisite", "unclear")
LEARNING_STATES = ("not_available", "calm", "confused", "disengaged")
UNKNOWN = "unknown_or_other"
UNSEEN = "__unseen__"
DEFAULT_BAND = "normal"
BANDS = ("normal", "sparse", "low_quality", "motor", "rendering", "motor_and_rendering")
# Bands in which the answer alone can never name a reason, whatever the learner's history. Motor
# and rendering only weaken the likelihood row; a rendering problem puts unknown_or_other on top.
UNCERTAIN_BANDS = ("sparse", "low_quality")

# How each game's belief hook reads its evidence, as the rules do today. The thresholds are the
# Sinhala packages' motor and rendering rules.
SIGNALS: dict[str, object] = {
    "response_time_missing": {"field": "response_time_ms", "missing": True},
    "summary_empty": {"field": "interaction_summary", "empty": True},
    "motor": {"any": {"correction_count": 3, "cancelled_drag_count": 2}},
    "rendering": {"equals": {"rendering_issue_reported": True}},
}
BAND_RULES: dict[str, list[dict[str, object]]] = {
    "timing": [{"band": "sparse", "when_all": ["response_time_missing"]}],
    "timing_and_summary": [
        {"band": "sparse", "when_all": ["response_time_missing", "summary_empty"]},
        {"band": "low_quality", "when_all": ["summary_empty"]},
    ],
    # Timing is ignored on purpose: accommodations must never make evidence weak.
    "sinhala_interaction": [
        {"band": "motor_and_rendering", "when_all": ["motor", "rendering"]},
        {"band": "motor", "when_all": ["motor"]},
        {"band": "rendering", "when_all": ["rendering"]},
    ],
}
# An unexplained answer is re-coded from interaction counts, first match wins. The re-coded label
# for each signal is read from the fixtures.
INTERACTION_REWRITE_SIGNALS: tuple[tuple[str, str, object], ...] = (
    ("started_from_ones", "equals", False),
    ("alignment_valid", "equals", False),
    ("invalid_exchange_count", "at_least", 1),
    ("operation_changes", "at_least", 1),
    ("story_reorder_count", "at_least", 1),
)
REWRITE_INPUT_PREFIX = "explained_by_"

# Expected valid Independence Gain by position in today's order: the first help gets the most.
FIRST_GAIN = 0.6
GAIN_DECREMENT = 0.05
# How many episodes of evidence the expert start is worth. With this spacing, the shared lead
# help gives way after two failed rounds or one helped-but-not-independent result, and another
# help takes the lead after two independent successes, as the rules' preference threshold does.
PRIOR_STRENGTH = 8
# Expert start for a child's own valid independent-success rate with a help on this skill: one
# own success puts even the last help first for that child, as the rules do today.
OWN_SUCCESS_RATE_GAIN = 0.3
# Predicted gains this close count as equal; the help earlier in the cell's order then wins.
TIE_TOLERANCE = 1e-9


# --- Evidence bands -------------------------------------------------------------------------


def signal_present(name: str, response_time_ms: int | None, summary: Mapping[str, object]) -> bool:
    """Whether one named signal fires for these inputs."""

    if name == "response_time_missing":
        return response_time_ms is None
    if name == "summary_empty":
        return not summary
    if name == "motor":
        thresholds = SIGNALS["motor"]["any"]  # type: ignore[index]
        return any(int(summary.get(field, 0) or 0) >= limit for field, limit in thresholds.items())
    if name == "rendering":
        return summary.get("rendering_issue_reported") is True
    raise KeyError(name)


def evidence_band(rule: str, response_time_ms: int | None, summary: Mapping[str, object]) -> str:
    for entry in BAND_RULES[rule]:
        if all(signal_present(name, response_time_ms, summary) for name in entry["when_all"]):  # type: ignore[union-attr]
            return str(entry["band"])
    return DEFAULT_BAND


def _band_rule(area: Mapping[str, object]) -> str:
    inputs = area["inputs"]
    if area["subject"] == "SIN":
        return "sinhala_interaction"
    return "timing_and_summary" if "timed_without_summary" in inputs else "timing"  # type: ignore[operator]


# --- Model 1 --------------------------------------------------------------------------------


def _top(codes: list[str], probabilities: list[float]) -> str:
    return codes[probabilities.index(max(probabilities))]


def _low_confidence(probabilities: list[float]) -> bool:
    ordered = sorted(probabilities, reverse=True)
    return ordered[0] < 0.4 or (len(ordered) > 1 and ordered[0] - ordered[1] < 0.1)


def _misconception_table(
    area: Mapping[str, object], beliefs: Mapping[str, object]
) -> dict[str, object]:
    area_id = str(area["area_id"])
    codes: list[str] = list(area["codes"])  # type: ignore[arg-type]
    unlisted = str(beliefs["unlisted_code"])
    rule = _band_rule(area)
    inputs: Mapping[str, Mapping[str, object]] = area["inputs"]  # type: ignore[assignment]
    records = [r for r in beliefs["game_belief"] if r["area_id"] == area_id]  # type: ignore[union-attr]

    rows: dict[str, dict[str, dict[str, float]]] = {}
    rewrite_inputs = []
    for record in records:
        if record["input"].startswith(REWRITE_INPUT_PREFIX):
            rewrite_inputs.append(record)
            continue
        given = inputs[record["input"]]
        band = evidence_band(rule, given["response_time_ms"], given["interaction_summary"])  # type: ignore[arg-type]
        key = UNSEEN if record["error_code"] == unlisted else record["error_code"]
        row = dict(zip(codes, record["belief"]["likelihood"], strict=True))
        if rows.setdefault(band, {}).setdefault(key, row) != row:
            raise ValueError(f"{area_id} gives two beliefs for {key} in band {band}")
    for band, by_code in rows.items():
        if set(by_code) != {*codes, UNSEEN}:
            raise ValueError(f"{area_id} band {band} misses a code")

    rewrites = []
    for record in rewrite_inputs:
        field = record["input"].removeprefix(REWRITE_INPUT_PREFIX)
        signal = next(s for s in INTERACTION_REWRITE_SIGNALS if s[0] == field)
        likelihood = dict(zip(codes, record["belief"]["likelihood"], strict=True))
        target = [code for code in codes if rows[DEFAULT_BAND][code] == likelihood]
        if len(target) != 1:
            raise ValueError(f"{area_id} rewrite {field} matches {target}")
        rewrites.append(
            {"field": field, "condition": signal[1], "value": signal[2], "error_code": target[0]}
        )
    rewrites.sort(key=lambda item: [s[0] for s in INTERACTION_REWRITE_SIGNALS].index(item["field"]))

    # Whether an answer whose own evidence puts unknown_or_other on top makes the reading
    # uncertain, whatever the learner prior then does, as the game shows.
    unknown_top = set()
    for record in records + [r for r in beliefs["learner_prior"] if r["area_id"] == area_id]:  # type: ignore[union-attr]
        given = inputs[record["input"]]
        band = evidence_band(rule, given["response_time_ms"], given["interaction_summary"])  # type: ignore[arg-type]
        if (
            band not in UNCERTAIN_BANDS
            and _top(codes, record["belief"]["likelihood"]) == UNKNOWN
            and not _low_confidence(record["belief"]["probabilities"])
        ):
            unknown_top.add(record["model1_uncertain"])
    if len(unknown_top) != 1:
        raise ValueError(f"{area_id} does not show how an unknown top label is read")

    return {
        "area_id": area_id,
        "subject": area["subject"],
        "game": area["game"],
        "catalogue_version": area["catalogue_version"],
        "source_model_version": area["model_version"],
        "source_package_sha256": area["package_sha256"],
        "codes": codes,
        "class_priors": dict.fromkeys(codes, 1.0),
        "evidence_band_rule": rule,
        "evidence_bands": [band for band in BANDS if band in rows],
        "error_likelihoods": {band: rows[band] for band in BANDS if band in rows},
        "interaction_rewrites": rewrites,
        "unknown_top_is_uncertain": unknown_top.pop(),
    }


def _misconception_settings(beliefs: Mapping[str, object]) -> dict[str, object]:
    return {
        "package_version": PACKAGE_VERSION,
        "evidence_status": EVIDENCE_STATUS,
        "default_band": DEFAULT_BAND,
        "bands": list(BANDS),
        "uncertain_bands": list(UNCERTAIN_BANDS),
        "signals": SIGNALS,
        "band_rules": BAND_RULES,
        "interaction_rewrite_scope": {
            "applies_to_error_code": UNKNOWN,
            "requires_interaction_summary": True,
            "first_match_wins": True,
        },
        "uncertainty_rule": {
            "top_probability_below": 0.4,
            "top_two_margin_below": 0.1,
            "uncertain_band": True,
            "unknown_top_of_the_answer_evidence_when_area_says": True,
            "unknown_code": UNKNOWN,
        },
        "learner_prior": {
            "source_version": beliefs["learner_prior_version"],
            "window": beliefs["learner_prior_cap"],
            "pseudocount": 1,
            "counts": "unaided before and after answers of this learner on this skill; supported "
            "answers never count; a correct answer keeps its place in the window",
            "update": "posterior proportional to likelihood times (1 + count of the code in the window)",
        },
    }


# --- Reason families ------------------------------------------------------------------------


def _reason_families(orders: Mapping[str, object]) -> dict[str, object]:
    subjects = {}
    for subject in SUBJECTS:
        source = orders["reason_families"][subject]  # type: ignore[index]
        subjects[subject] = {
            "labels": {
                label: {
                    "reason_family": row["reason_family"],
                    "decided_by": row["decided_by"],
                    "needs_review": row["decided_by"] == "no_match",
                    "games": row["games"],
                }
                for label, row in source["labels"].items()
            },
            "missing_label": source["missing_label"],
        }
    return {
        "package_version": PACKAGE_VERSION,
        "evidence_status": EVIDENCE_STATUS,
        "reason_families": list(REASON_FAMILIES),
        "needs_review_note": "Labels that no pattern matched fall back to unclear. They keep that "
        "family until a teacher reviews them.",
        "subjects": subjects,
    }


# --- Model 2 --------------------------------------------------------------------------------


def _gains(order: list[str]) -> dict[str, float]:
    return {
        support: round(FIRST_GAIN - GAIN_DECREMENT * position, 10)
        for position, support in enumerate(order)
    }


def _support_gains(orders: Mapping[str, object]) -> dict[str, object]:
    decisions = [
        d
        for d in orders["decisions"]  # type: ignore[union-attr]
        if d["condition"] == "proposed" and d["helps"] == "all_eligible" and d["history"] == "none"
    ]
    families = orders["reason_families"]
    cells = []
    for subject in SUBJECTS:
        found: dict[tuple[str, bool, str], list[str]] = {}
        for decision in (d for d in decisions if d["subject"] == subject):
            family = (
                "unclear"
                if decision["model1_uncertain"]
                else families[subject]["labels"][decision["model1_label"]]["reason_family"]  # type: ignore[index]
            )
            order = (
                decision["delivered"]["support_order"]
                if subject == "SIN"
                else decision["decision"]["support_order"]
            )
            key = (family, decision["model1_uncertain"], decision["learning_state"])
            if found.setdefault(key, order) != order:
                raise ValueError(f"{subject} {key} has two orders")
        sinhala_orders = {tuple(order) for order in found.values()}
        if subject == "SIN" and len(sinhala_orders) != 1:
            raise ValueError("Sinhala no longer delivers one order for every reason")
        for family in REASON_FAMILIES:
            for uncertain in (False, True):
                if uncertain and family != "unclear":
                    continue
                for state in LEARNING_STATES:
                    key = (family, uncertain, state)
                    if key in found:
                        order, source = found[key], "frozen_order"
                    elif subject == "SIN":
                        # No Sinhala label falls in this family; Sinhala delivers one order anyway.
                        order, source = (
                            list(next(iter(sinhala_orders))),
                            "sinhala_delivered_sequence",
                        )
                    else:
                        raise ValueError(f"{subject} {key} is missing from the fixtures")
                    cells.append(
                        {
                            "subject": subject,
                            "reason_family": family,
                            "model1_uncertain": uncertain,
                            "learning_state": state,
                            "source": source,
                            "order": order,
                            "expected_gain": _gains(order),
                        }
                    )
    return {
        "package_version": PACKAGE_VERSION,
        "evidence_status": EVIDENCE_STATUS,
        "meaning": "Expected valid Independence Gain of each help type before any child's data. "
        "Sorting the drawable helps by it gives today's order.",
        "first_gain": FIRST_GAIN,
        "gain_decrement": GAIN_DECREMENT,
        "prior_strength": PRIOR_STRENGTH,
        "own_success_rate_gain": OWN_SUCCESS_RATE_GAIN,
        "tie_tolerance": TIE_TOLERANCE,
        "tie_rule": "Gains within tie_tolerance of each other count as equal; the help earlier in "
        "the cell's order wins.",
        "help_types": {subject: orders["subject_orders"][subject] for subject in SUBJECTS},  # type: ignore[index]
        "learning_states": list(LEARNING_STATES),
        "cells": cells,
        "unused_reference": {
            "SIN": {
                "lead_by_reason": orders["lead_by_reason"]["SIN"],  # type: ignore[index]
                "note": "The Sinhala rule computes a lead help per reason, but the games deliver "
                "the authored sequence instead. Kept for reference; not used for the expert start.",
            }
        },
    }


# --- Files ----------------------------------------------------------------------------------


def _text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_fixture(name: str) -> tuple[dict[str, object], str]:
    text = (FIXTURE_DIRECTORY / name).read_text(encoding="utf-8")
    return json.loads(text), text


def build_package() -> dict[str, str]:
    """Package-relative path to its exact text, the manifest excluded."""

    beliefs, _ = _read_fixture(BELIEFS_FIXTURE)
    orders, _ = _read_fixture(ORDERS_FIXTURE)
    files = {
        f"misconception_tables/{area['area_id']}.json": _text(_misconception_table(area, beliefs))
        for area in beliefs["areas"]  # type: ignore[union-attr]
    }
    files["misconception_settings.json"] = _text(_misconception_settings(beliefs))
    files["reason_families.json"] = _text(_reason_families(orders))
    files["support_gains.json"] = _text(_support_gains(orders))
    return dict(sorted(files.items()))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def build_manifest(files: Mapping[str, str]) -> dict[str, object]:
    fixtures = FIXTURE_DIRECTORY.relative_to(ROOT).as_posix()
    if _git("status", "--porcelain", "--", fixtures):
        raise SystemExit("the reference fixtures have uncommitted changes")
    return {
        "package_version": PACKAGE_VERSION,
        "evidence_status": EVIDENCE_STATUS,
        "reviewed_by": None,
        "review_status": "unreviewed",
        "development_only": True,
        "generator": "tools/gamification/datasets/build_expert_model_data.py",
        # The last commit that changed the reference fixtures this package is built from.
        "source_commit": _git("log", "-1", "--format=%H", "--", fixtures),
        "reference_fixtures": {
            name: _sha256(_read_fixture(name)[1]) for name in (BELIEFS_FIXTURE, ORDERS_FIXTURE)
        },
        "files": {path: _sha256(text) for path, text in files.items()},
    }


def check(directory: Path = OUTPUT_DIRECTORY) -> list[str]:
    files = build_package()
    problems = [
        f"{path} differs from a fresh build"
        for path, text in files.items()
        if not (directory / path).is_file() or (directory / path).read_text("utf-8") != text
    ]
    stored = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*.json")
        if path.name != "manifest.json"
    }
    problems += [f"{path} is not part of the package" for path in sorted(stored - set(files))]
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    if manifest != build_manifest(files):
        problems.append("manifest.json differs from a fresh build")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a file is stale")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIRECTORY)
    arguments = parser.parse_args()
    if arguments.check:
        problems = check(arguments.output_dir)
        print("\n".join(problems) or "expert model data matches a fresh build")
        return 1 if problems else 0
    files = build_package()
    for path, text in files.items():
        target = arguments.output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (arguments.output_dir / "manifest.json").write_text(
        _text(build_manifest(files)), encoding="utf-8"
    )
    print(f"wrote {len(files)} files and manifest.json to {arguments.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
