"""Development-only Theme 3 plant vocabulary content for G5-AREA-ENG-03."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-03"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-plant-explorer-draft-v1"
CATALOGUE_VERSION = "g5-eng-plant-misconceptions-v1"
FEATURE_VERSION = "g5-eng-plant-features-v1"
MAPPING_VERSION = "g5-eng-plant-source-mapping-v1"
MODEL_VERSION = "g5-eng-plant-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-plant-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-plant-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-plant-parallel-v1"

Chapter = Literal["garden_word_hunt", "build_a_plant", "one_or_many"]
Role = Literal["unsupported_before", "unsupported_after"]

VOCABULARY = (
    ("roots", "Roots", "plant-roots"),
    ("flowers", "Flowers", "plant-flowers"),
    ("fruits", "Fruits", "plant-fruits"),
    ("leaves", "Leaves", "plant-leaves"),
    ("buds", "Buds", "plant-buds"),
    ("petals", "Petals", "plant-petals"),
)
PARTS_YOUNG = (
    ("roots", "Roots", "roots-slot"),
    ("stem", "Stem", "stem-slot"),
    ("leaves", "Leaves", "leaves-slot"),
    ("bud", "Bud", "bud-slot"),
    ("petals", "Petals", "petals-slot"),
    ("fruit", "Fruits", "fruit-slot"),
)
PARTS_TREE = (
    ("roots", "Roots", "roots-slot"),
    ("trunk", "Trunk", "trunk-slot"),
    ("branches", "Branches", "branches-slot"),
    ("leaves", "Leaves", "leaves-slot"),
    ("flowers", "Flowers", "flowers-slot"),
    ("fruits", "Fruits", "fruits-slot"),
)
NUMBER_PAIRS = (
    ("leaf", "Leaf", "Leaves"),
    ("branch", "Branch", "Branches"),
    ("bud", "Bud", "Buds"),
)
MISCONCEPTIONS = (
    "plant_type_vs_plant_part_confusion",
    "root_vs_stem_confusion",
    "stem_vs_trunk_confusion",
    "branch_vs_stem_confusion",
    "leaf_vs_petal_confusion",
    "flower_vs_bud_confusion",
    "flower_vs_fruit_confusion",
    "large_vs_small_plant_confusion",
    "climber_vs_creeper_confusion",
    "bush_vs_tree_form_confusion",
    "singular_plural_number_confusion",
    "leaf_leaves_irregular_form_confusion",
    "branch_branches_es_ending_confusion",
    "bud_buds_s_ending_confusion",
    "incomplete_mapping_or_omission",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-ENG-PLANT-VOCAB-01",
        "garden_word_hunt",
        "පැළෑටි වචන හඳුනාගැනීම",
        "easy",
        "plant_vocabulary_mapping",
    ),
    AtomicSkill(
        "G5-ENG-PLANT-PARTS-02",
        "build_a_plant",
        "පැළෑටි කොටස් නම් කිරීම",
        "medium",
        "plant_part_labeling",
    ),
    AtomicSkill(
        "G5-ENG-PLANT-NUMBER-03",
        "one_or_many",
        "ඒකවචන සහ බහුවචන හඳුනාගැනීම",
        "medium-hard",
        "singular_plural_pairing",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class PlantExplorerItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Role
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _token(prefix: str, value: str, salt: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def generate_item(skill_id: str, *, role: str, seed: int) -> PlantExplorerItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("PLANT_EXPLORER_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    if skill.chapter == "garden_word_hunt":
        rows = list(VOCABULARY)
        rng.shuffle(rows)
        rows = rows[:4]
        words = [
            {"word_token": _token("w", key, salt), "text_en": text} for key, text, _target in rows
        ]
        targets = [
            {"target_token": _token("t", target, salt), "visual_key": target}
            for _key, _text, target in reversed(rows)
        ]
        answer = {_token("w", key, salt): _token("t", target, salt) for key, _text, target in rows}
        game: dict[str, object] = {
            "response_kind": "plant_vocabulary_mapping",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "words": words,
            "targets": targets,
            "target_mapping": answer,
            "scene_asset": "plant-garden-playfield.png",
        }
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන පැළෑටි කොටසට සම්බන්ධ කරන්න."
    elif skill.chapter == "build_a_plant":
        rows = list(PARTS_YOUNG if seed % 2 == 0 else PARTS_TREE)
        rng.shuffle(rows)
        rows = rows[:4]
        labels = [
            {"label_token": _token("l", key, salt), "text_en": text} for key, text, _slot in rows
        ]
        parts = [
            {"part_token": _token("p", slot, salt), "visual_key": slot}
            for _key, _text, slot in reversed(rows)
        ]
        answer = {_token("p", slot, salt): _token("l", key, salt) for key, _text, slot in rows}
        game = {
            "response_kind": "plant_part_labeling",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "labels": labels,
            "parts": parts,
            "target_mapping": answer,
            "scene_asset": "plant-parts-young-plant.png"
            if seed % 2 == 0
            else "plant-parts-tree.png",
        }
        prompt = "ඉංග්‍රීසි නම් නිවැරදි පැළෑටි කොටස්වලට තබන්න."
    else:
        concepts = [
            {
                "concept_token": _token("c", key, salt),
                "concept_key": key,
                "single_asset": f"{key}-single.png",
                "multiple_asset": f"{key}-multiple.png",
            }
            for key, _single, _plural in NUMBER_PAIRS
        ]
        forms = []
        answer = {}
        for key, single, plural in NUMBER_PAIRS:
            single_token = _token("f", f"{key}:one", salt)
            plural_token = _token("f", f"{key}:many", salt)
            forms.extend(
                (
                    {"form_token": single_token, "text_en": single},
                    {"form_token": plural_token, "text_en": plural},
                )
            )
            answer[_token("c", key, salt)] = {
                "singular_form_token": single_token,
                "plural_form_token": plural_token,
            }
        rng.shuffle(forms)
        game = {
            "response_kind": "singular_plural_pairing",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "concepts": concepts,
            "forms": forms,
            "target_pairs": answer,
        }
        prompt = "එකක් සහ බොහෝ දේ සඳහා නිවැරදි ඉංග්‍රීසි වචන තබන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return PlantExplorerItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:parallel-v1",
        skill_id,
        skill.chapter,
        role,
        prompt,
        (),
        "constructed-response",
        {},
        game,
    )  # type: ignore[arg-type]


def public_game_data(item: PlantExplorerItem) -> dict[str, object]:
    hidden = {"target_mapping", "target_pairs"}
    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key not in hidden},
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {
        "command_token": str(game["command_token"]),
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }
    if game["response_kind"] == "plant_vocabulary_mapping":
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        return {
            "kind": "plant_vocabulary_mapping",
            **common,
            "placements": [
                {"sequence": index + 1, "word_token": word, "target_token": target}
                for index, (word, target) in enumerate(mapping.items())
            ],
            "unplaced_word_tokens": [],
        }
    if game["response_kind"] == "plant_part_labeling":
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        return {
            "kind": "plant_part_labeling",
            **common,
            "labels": [
                {"sequence": index + 1, "part_token": part, "label_token": label}
                for index, (part, label) in enumerate(mapping.items())
            ],
            "unfilled_part_tokens": [],
        }
    pairs = game["target_pairs"]
    assert isinstance(pairs, Mapping)
    return {
        "kind": "singular_plural_pairing",
        **common,
        "pairs": [{"concept_token": concept, **dict(forms)} for concept, forms in pairs.items()],
    }


def validate_constructed_response(
    item: Mapping[str, object] | PlantExplorerItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, PlantExplorerItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_PLANT_EXPLORER_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != game["response_kind"]:
        raise ValueError("MALFORMED_PLANT_EXPLORER_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_PLANT_EXPLORER_COMMAND")
    trace = response.get("interaction_trace")
    if (
        not isinstance(trace, list)
        or not trace
        or not all(isinstance(value, str) for value in trace)
    ):
        raise ValueError("INVALID_PLANT_EXPLORER_TRACE")
    kind = str(game["response_kind"])
    if kind == "plant_vocabulary_mapping":
        rows = response["placements"]
        if not isinstance(rows, list) or response["unplaced_word_tokens"] != []:
            raise ValueError("INCOMPLETE_PLANT_VOCABULARY_MAPPING")
        submitted = {
            str(row["word_token"]): str(row["target_token"])
            for row in rows
            if isinstance(row, Mapping)
        }
        if len(submitted) != len(rows) or set(submitted) != set(game["target_mapping"]):  # type: ignore[arg-type]
            raise ValueError("INCOMPLETE_OR_DUPLICATE_PLANT_MAPPING")
        correct = submitted == game["target_mapping"]
        error = "plant_type_vs_plant_part_confusion"
    elif kind == "plant_part_labeling":
        rows = response["labels"]
        if not isinstance(rows, list) or response["unfilled_part_tokens"] != []:
            raise ValueError("INCOMPLETE_PLANT_PART_LABELING")
        submitted = {
            str(row["part_token"]): str(row["label_token"])
            for row in rows
            if isinstance(row, Mapping)
        }
        if len(submitted) != len(rows) or set(submitted) != set(game["target_mapping"]):  # type: ignore[arg-type]
            raise ValueError("INCOMPLETE_OR_DUPLICATE_PART_LABELING")
        correct = submitted == game["target_mapping"]
        error = "root_vs_stem_confusion"
    else:
        rows = response["pairs"]
        if not isinstance(rows, list):
            raise ValueError("INCOMPLETE_SINGULAR_PLURAL_PAIRING")
        submitted = {
            str(row["concept_token"]): {
                "singular_form_token": str(row["singular_form_token"]),
                "plural_form_token": str(row["plural_form_token"]),
            }
            for row in rows
            if isinstance(row, Mapping)
        }
        if len(submitted) != len(rows) or set(submitted) != set(game["target_pairs"]):  # type: ignore[arg-type]
            raise ValueError("INCOMPLETE_OR_DUPLICATE_NUMBER_PAIRING")
        correct = submitted == game["target_pairs"]
        error = "singular_plural_number_confusion"
    return correct, "correct" if correct else error, dict(response)


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {key: confidence if key == primary else remainder for key in MISCONCEPTIONS}
    return {
        "probabilities": probabilities,
        "predicted_label": primary,
        "confidence": probabilities[primary],
        "fallback_used": sparse,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int
) -> dict[str, object]:
    del skill_id, seed
    return {
        "selected_action": "visual_guidance",
        "condition": condition,
        "propensity": 1.0,
        "policy_version": POLICY_VERSION,
        "eligible_actions": list(SCAFFOLDS),
        "belief_label": belief.get("predicted_label"),
    }


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if scaffold_type == "visual_guidance":
        return ["පැළෑටි රූපයේ හැඩය, පිහිටීම හෝ ගණන හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "රූපයේ ගැළපෙන කොටස හඳුනාගනිමු.", "වචනය තබා සම්බන්ධය පරීක්ෂා කරමු."]
    return ["එක් වචනයක් තෝරන්න.", "එහි අර්ථය, කොටස හෝ ගණන බලන්න.", "ගැළපෙන තැනට තබා සියල්ල නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "area": AREA_ID,
                "version": PACKAGE_VERSION,
                "skills": list(SKILLS),
                "vocabulary": [row[0] for row in VOCABULARY],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
