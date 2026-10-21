"""Development-only Theme 4 animal vocabulary content for G5-AREA-ENG-04."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.gamification.content.simpler_items import simpler_matching_item

AREA_ID = "G5-AREA-ENG-04"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-wildlife-ranger-draft-v1"
CATALOGUE_VERSION = "g5-eng-animal-misconceptions-v1"
FEATURE_VERSION = "g5-eng-animal-features-v1"
MAPPING_VERSION = "g5-eng-animal-source-mapping-v1"
MODEL_VERSION = "g5-eng-animal-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-animal-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-animal-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-animal-parallel-v1"

Chapter = Literal["animal_spotter", "lesson_trail_sort", "body_part_detective"]
Role = Literal["unsupported_before", "unsupported_after"]

# Only reviewed, unambiguous active forms are used. Source anomalies stay in review metadata.
ANIMALS = (
    ("dog", "Dog", "dog"),
    ("elephant", "Elephant", "elephant"),
    ("rabbit", "Rabbit", "rabbit"),
    ("peacock", "Peacock", "peacock"),
    ("butterfly", "Butterfly", "butterfly"),
    ("cow", "Cow", "cow"),
    ("monkey", "Monkey", "monkey"),
    ("owl", "Owl", "owl"),
)
ANIMAL_SPRITES = {key: index for index, (key, _text, _visual) in enumerate(ANIMALS)}
LESSON_GROUPS = {
    "animals": ("Dog", "Elephant", "Rabbit", "Cow"),
    "birds": ("Parrot", "Peacock", "Crow", "Owl"),
    "insects": ("Ant", "Butterfly", "Mosquito", "Moth"),
}
BODY_PARTS = (
    ("eyes", "Eyes", "eyes-slot"),
    ("mouth", "Mouth", "mouth-slot"),
    ("tail", "Tail", "tail-slot"),
    ("trunk", "Trunk", "trunk-slot"),
)
MISCONCEPTIONS = (
    "animal_word_visual_confusion",
    "animal_reptile_lesson_heading_confusion",
    "bird_animal_lesson_heading_confusion",
    "bird_insect_lesson_heading_confusion",
    "textbook_heading_overgeneralization",
    "beak_vs_mouth_confusion",
    "horns_vs_antenna_confusion",
    "fins_vs_wings_confusion",
    "tail_vs_trunk_confusion",
    "whiskers_vs_fur_confusion",
    "nose_vs_trunk_confusion",
    "claws_vs_hoof_confusion",
    "cockscomb_vs_crest_confusion",
    "singular_plural_form_interference",
    "source_spelling_normalization_confusion",
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
    AtomicSkill("G5-ENG-ANIMAL-VOCAB-01", "animal_spotter", "සත්ව වචන හඳුනාගැනීම", "easy", "animal_vocabulary_mapping"),
    AtomicSkill("G5-ENG-ANIMAL-GROUP-02", "lesson_trail_sort", "පාඩමේ කාණ්ඩවලට වචන තැබීම", "medium", "lesson_heading_sort"),
    AtomicSkill("G5-ENG-ANIMAL-PARTS-03", "body_part_detective", "සත්ව ශරීර කොටස් නම් කිරීම", "medium-hard", "animal_part_labeling"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class WildlifeRangerItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> WildlifeRangerItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("WILDLIFE_RANGER_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    if skill.chapter == "animal_spotter":
        rows = list(ANIMALS)
        rng.shuffle(rows)
        rows = rows[:4]
        entries = [{"entry_token": _token("w", key, salt), "text_en": text} for key, text, _ in rows]
        targets = [{"target_token": _token("a", visual, salt), "sprite_index": ANIMAL_SPRITES[visual]} for _, _, visual in reversed(rows)]
        answer = {_token("w", key, salt): _token("a", visual, salt) for key, _, visual in rows}
        game: dict[str, object] = {
            "response_kind": "animal_vocabulary_mapping",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "entries": entries,
            "targets": targets,
            "target_mapping": answer,
            "scene_asset": "wildlife-ranger-playfield.png",
        }
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන සතාට සම්බන්ධ කරන්න."
    elif skill.chapter == "lesson_trail_sort":
        selected = {group: list(values)[:2] for group, values in LESSON_GROUPS.items()}
        entries = []
        headings = []
        answer = {}
        for group, values in selected.items():
            heading_token = _token("h", group, salt)
            headings.append({"heading_token": heading_token, "text_en": group.title()})
            for text in values:
                entry_token = _token("e", text, salt)
                entries.append({"entry_token": entry_token, "text_en": text})
                answer[entry_token] = heading_token
        rng.shuffle(entries)
        rng.shuffle(headings)
        game = {
            "response_kind": "lesson_heading_sort",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "entries": entries,
            "targets": headings,
            "target_mapping": answer,
            "scene_asset": "animal-lesson-trails.png",
        }
        prompt = "මේ පාඩමේ එන ශීර්ෂයට සත්ව වචනය තබන්න."
    else:
        rows = list(BODY_PARTS)
        rng.shuffle(rows)
        rows = rows[:4]
        entries = [{"entry_token": _token("l", key, salt), "text_en": text} for key, text, _ in rows]
        positions = {"eyes-slot": (27, 25), "mouth-slot": (25, 39), "trunk-slot": (11, 53), "tail-slot": (89, 48)}
        targets = [{"target_token": _token("p", slot, salt), "marker_index": index + 1, "x_percent": positions[slot][0], "y_percent": positions[slot][1]} for index, (_, _, slot) in enumerate(reversed(rows))]
        answer = {_token("l", key, salt): _token("p", slot, salt) for key, _, slot in rows}
        game = {
            "response_kind": "animal_part_labeling",
            "activity_id": skill.chapter,
            "command_token": command_token,
            "entries": entries,
            "targets": targets,
            "target_mapping": answer,
            "scene_asset": "animal-body-elephant.png",
        }
        prompt = "ඉංග්‍රීසි නම් නිවැරදි සත්ව ශරීර කොටස්වලට තබන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return WildlifeRangerItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]

def generate_simpler_item(skill_id: str, *, seed: int, than: Mapping[str, object]) -> WildlifeRangerItem | None:
    """The same game and skill with fewer pairs to link than the failed game, from a fresh item."""

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    return simpler_matching_item(item, than=than)



def public_game_data(item: WildlifeRangerItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key != "target_mapping"}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    kind = str(game["response_kind"])
    row_key = "placements" if kind != "animal_part_labeling" else "labels"
    empty_key = "unplaced_entry_tokens" if kind != "animal_part_labeling" else "unfilled_part_tokens"
    return {
        "kind": kind,
        "command_token": str(game["command_token"]),
        row_key: [
            {"sequence": index + 1, "entry_token": source, "target_token": target}
            for index, (source, target) in enumerate(mapping.items())
        ],
        empty_key: [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }


def validate_constructed_response(item: Mapping[str, object] | WildlifeRangerItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, WildlifeRangerItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_WILDLIFE_RANGER_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != game["response_kind"]:
        raise ValueError("MALFORMED_WILDLIFE_RANGER_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_WILDLIFE_RANGER_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_WILDLIFE_RANGER_TRACE")
    kind = str(game["response_kind"])
    row_key = "labels" if kind == "animal_part_labeling" else "placements"
    empty_key = "unfilled_part_tokens" if kind == "animal_part_labeling" else "unplaced_entry_tokens"
    rows = response[row_key]
    if not isinstance(rows, list) or response[empty_key] != []:
        raise ValueError("INCOMPLETE_WILDLIFE_RANGER_MAPPING")
    submitted = {str(row["entry_token"]): str(row["target_token"]) for row in rows if isinstance(row, Mapping)}
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    if len(submitted) != len(rows) or set(submitted) != set(answer):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_WILDLIFE_MAPPING")
    correct = submitted == answer
    error = {
        "animal_vocabulary_mapping": "animal_word_visual_confusion",
        "lesson_heading_sort": "textbook_heading_overgeneralization",
        "animal_part_labeling": "tail_vs_trunk_confusion",
    }[kind]
    return correct, "correct" if correct else error, dict(response)


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {key: confidence if key == primary else remainder for key in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    del game
    if scaffold_type == "visual_guidance":
        return ["සතාගේ හැඩය හෝ පෙන්වා ඇති ශරීර කොටස හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "නව රූපයේ ගැළපෙන අර්ථය සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් වචනයක් තෝරන්න.", "රූපය හෝ පාඩම් ශීර්ෂය බලන්න.", "ගැළපෙන තැනට තබා සියල්ල නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "skills": list(SKILLS), "animals": [row[0] for row in ANIMALS]}, sort_keys=True).encode()).hexdigest()
