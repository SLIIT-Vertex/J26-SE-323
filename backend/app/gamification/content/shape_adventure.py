"""Grade 5 shapes, solids, orientation and nets activities."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-13"
UNIVERSAL_SKILL_ID = "MAT-SHP"
PACKAGE_VERSION = "g5-mat-shape-adventure-v1"
CATALOGUE_VERSION = "g5-mat-shape-misconceptions-v1"
FEATURE_VERSION = "g5-mat-shape-features-v1"
MAPPING_VERSION = "g5-mat-shape-source-mapping-v1"
MODEL_VERSION = "g5-mat-shape-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-shape-deterministic-support-v1"
SCORING_VERSION = "g5-mat-shape-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-shape-parallel-v1"
Chapter = Literal["shape_table", "orientation_lab", "solid_net_match"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-SHAPE-TABLE-01", "shape_table", "හැඩතල වගුව පුරවමු", "easy", "shape_property_table"),
    AtomicSkill("G5-MAT-ORIENTATION-01", "orientation_lab", "තිරස් හා සිරස් හඳුනාගනිමු", "medium", "orientation_identification"),
    AtomicSkill("G5-MAT-SOLID-NET-01", "solid_net_match", "ඝන වස්තුවට පතරොම ගළපමු", "hard", "solid_net_match"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
SOLIDS = ("cube", "cuboid", "cylinder", "triangular_pyramid")
PROPERTIES = {
    "cube": (6, 8, 12),
    "cuboid": (6, 8, 12),
    "cylinder": (2, 0, 2),
    "triangular_pyramid": (4, 4, 6),
}
ORIENTATIONS = {
    "spirit_level": "horizontal",
    "shelf": "horizontal",
    "plumb_line": "vertical",
    "wall_edge": "vertical",
}
MISCONCEPTIONS = (
    "faces_edges_vertices_confused", "curved_surface_as_flat_face", "cylinder_has_vertices",
    "cube_cuboid_properties_confused", "horizontal_vertical_reversed", "spirit_level_misread",
    "plumb_line_misread", "cube_cuboid_net_confused", "cylinder_net_missing_circle",
    "triangular_pyramid_net_confused", "incomplete_match", "correct_result_invalid_working",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class ShapeItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Literal["unsupported_before", "unsupported_after"]
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_item(skill_id: str, *, role: str, seed: int) -> ShapeItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("SHAPE_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "shape_property_table":
        rows = list(SOLIDS)
        if role == "unsupported_after": rows = rows[1:] + rows[:1]
        game: dict[str, object] = {"response_kind": skill.response_kind, "row_ids": rows, "property_fields": ["faces", "vertices", "edges"]}
        prompt = "රූප බලමින් මුහුණත්, ශීර්ෂ සහ දාර ගණන වගුවේ පුරවන්න."
    elif skill.response_kind == "orientation_identification":
        examples = list(ORIENTATIONS)
        rng.shuffle(examples)
        game = {"response_kind": skill.response_kind, "example_ids": examples}
        prompt = "එක් එක් රූපයේ පෙන්වන දිශාව තිරස් ද සිරස් ද තෝරන්න."
    else:
        nets = list(SOLIDS)
        rng.shuffle(nets)
        game = {"response_kind": skill.response_kind, "solid_ids": list(SOLIDS), "net_ids": nets}
        prompt = "ඝන වස්තුව තෝරා එය සාදන නිවැරදි පතරොමට ගළපන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return ShapeItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "shape_property_table":
        rows = [
            {"solid_id": solid, "faces": PROPERTIES[solid][0], "vertices": PROPERTIES[solid][1], "edges": PROPERTIES[solid][2]}
            for solid in game["row_ids"]  # type: ignore[union-attr]
        ]
        return {"kind": kind, "rows": rows, "filled_cells": [f"{row['solid_id']}:{field}" for row in rows for field in ("faces", "vertices", "edges")]}
    if kind == "orientation_identification":
        return {"kind": kind, "selections": [{"example_id": example, "orientation": ORIENTATIONS[example]} for example in game["example_ids"]]}  # type: ignore[union-attr]
    return {
        "kind": kind,
        "matches": [{"solid_id": solid, "net_id": solid} for solid in game["solid_ids"]],  # type: ignore[union-attr]
        "interaction_trace": [f"match:{solid}:{solid}" for solid in game["solid_ids"]],  # type: ignore[union-attr]
    }


def _valid_rows(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(row, Mapping) and set(row) == {"solid_id", "faces", "vertices", "edges"} and all(type(row[key]) is int and 0 <= row[key] <= 20 for key in ("faces", "vertices", "edges")) for row in value)


def validate_constructed_response(item: Mapping[str, object] | ShapeItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, ShapeItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected, kind = correct_response(game), str(game["response_kind"])
    if response.get("kind") != kind: raise ValueError("WRONG_RESPONSE_KIND")
    if set(response) != set(expected): raise ValueError("MALFORMED_SHAPE_RESPONSE")
    normalized = dict(response)
    if kind == "shape_property_table":
        if not _valid_rows(response.get("rows")) or not isinstance(response.get("filled_cells"), list): raise ValueError("INVALID_SHAPE_TABLE")
        rows = response["rows"]
        first = next((index for index, row in enumerate(rows) if index >= len(expected["rows"]) or row != expected["rows"][index]), None)  # type: ignore[arg-type]
        if first is None and response.get("filled_cells") != expected["filled_cells"]: error = "correct_result_invalid_working"
        elif first is not None:
            row = rows[first]
            if row.get("solid_id") == "cylinder" and row.get("vertices") != 0: error = "cylinder_has_vertices"
            elif row.get("faces") in {8, 12} or row.get("edges") in {4, 6, 8}: error = "faces_edges_vertices_confused"
            else: error = "cube_cuboid_properties_confused"
            normalized["_feedback_column"] = f"{row.get('solid_id')}:{next((field for field in ('faces','vertices','edges') if row.get(field) != expected['rows'][first][field]), 'faces')}"  # type: ignore[index]
        else: error = "correct"
        correct = response == expected
        return correct, "correct" if correct else error, normalized
    if kind == "orientation_identification":
        selections = response.get("selections")
        if not isinstance(selections, list) or not all(isinstance(row, Mapping) and set(row) == {"example_id", "orientation"} and row["orientation"] in {"horizontal", "vertical"} for row in selections): raise ValueError("INVALID_ORIENTATION_RESPONSE")
        first = next((index for index, row in enumerate(selections) if index >= len(expected["selections"]) or row != expected["selections"][index]), None)  # type: ignore[arg-type]
        normalized["_feedback_column"] = str(selections[first].get("example_id", "orientation")) if first is not None and first < len(selections) else "orientation"
        correct = response == expected
        return correct, "correct" if correct else "horizontal_vertical_reversed", normalized
    matches, trace = response.get("matches"), response.get("interaction_trace")
    if not isinstance(matches, list) or not isinstance(trace, list) or not all(isinstance(row, Mapping) and set(row) == {"solid_id", "net_id"} for row in matches) or not all(isinstance(value, str) for value in trace): raise ValueError("INVALID_NET_MATCH_RESPONSE")
    first = next((row for index, row in enumerate(matches) if index >= len(expected["matches"]) or row != expected["matches"][index]), None)  # type: ignore[arg-type]
    normalized["_feedback_column"] = str(first.get("solid_id", "nets")) if first else "nets"
    correct = matches == expected["matches"] and bool(trace)
    error = "incomplete_match" if len(matches) != len(SOLIDS) else ("cylinder_net_missing_circle" if first and first.get("solid_id") == "cylinder" else "triangular_pyramid_net_confused" if first and first.get("solid_id") == "triangular_pyramid" else "cube_cuboid_net_confused")
    return correct, "correct" if correct else error, normalized


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = .8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(.72, max(.2, evidence_quality * .72))
    other = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else other for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = str(game["response_kind"])
    if scaffold_type == "visual_guidance":
        return {"shape_property_table": ["රූපයේ අංක යොදා ඇති මුහුණත්, ශීර්ෂ සහ දාර වෙන වෙනම බලන්න."], "orientation_identification": ["පොළොවට සමාන්තර රේඛාව තිරස්ය; ඉහළ සිට පහළට යන රේඛාව සිරස්ය."], "solid_net_match": ["ඝන වස්තුවේ එක් එක් මුහුණ පතරොමේ කොතැන තිබේද බලන්න."]}[kind]
    if kind == "shape_property_table": return ["එක් හැඩයක් තෝරමු.", "පැතලි මුහුණත් ගණන් කරමු.", "කොන් හමුවන ශීර්ෂ ගණන් කරමු.", "මුහුණත් හමුවන දාර ගණන් කර වගුව පුරවමු."]
    if kind == "orientation_identification": return ["උදාහරණ රූපයේ ප්‍රධාන රේඛාව බලමු.", "වමේ සිට දකුණට නම් තිරස් තෝරමු.", "ඉහළ සිට පහළට නම් සිරස් තෝරමු."]
    return ["ඝන වස්තුවේ මුහුණත්වල හැඩ බලමු.", "පතරොමේ එම මුහුණත් සියල්ල තිබේද බලමු.", "නැමූ විට හමුවන දාර සසඳමු.", "වස්තුව සහ නිවැරදි පතරොම ගළපමු."]


def package_hash() -> str:
    payload = {"area_id": AREA_ID, "package_version": PACKAGE_VERSION, "skills": [skill.__dict__ if hasattr(skill, "__dict__") else {"skill_id": skill.skill_id, "chapter": skill.chapter, "name_si": skill.name_si, "difficulty": skill.difficulty, "response_kind": skill.response_kind} for skill in ATOMIC_SKILLS], "properties": PROPERTIES}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
