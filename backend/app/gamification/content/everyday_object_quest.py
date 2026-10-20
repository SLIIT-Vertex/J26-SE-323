"""Development-only Theme 5 everyday-object vocabulary for G5-AREA-ENG-05."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-05"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-everyday-object-quest-draft-v1"
CATALOGUE_VERSION = "g5-eng-object-misconceptions-v1"
FEATURE_VERSION = "g5-eng-object-features-v1"
MAPPING_VERSION = "g5-eng-object-source-mapping-v1"
MODEL_VERSION = "g5-eng-object-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-object-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-object-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-object-parallel-v1"

Chapter = Literal["object_pop", "two_room_tidy", "name_builder"]
Role = Literal["unsupported_before", "unsupported_after"]

OBJECTS = (
    ("chair", "Chair", 0, "classroom"),
    ("pencil", "Pencil", 1, "classroom"),
    ("ruler", "Ruler", 2, "classroom"),
    ("bed", "Bed", 3, "home"),
    ("spoon", "Spoon", 4, "home"),
    ("toothbrush", "Toothbrush", 5, "home"),
    ("broom", "Broom", 6, "home"),
    ("plate", "Plate", 7, "home"),
)
MULTIWORD_NAMES = (
    ("text-book", ("Text", "Book"), 8),
    ("work-book", ("Work", "Book"), 9),
    ("lunch-box", ("Lunch", "box"), 10),
    ("record-book", ("Record", "Book"), 11),
    ("pencil-sharpener", ("Pencil", "Sharpener"), 12),
    ("stapler-machine", ("Stapler", "Machine"), 13),
)
MISCONCEPTIONS = (
    "object_word_visual_confusion",
    "classroom_home_lesson_heading_confusion",
    "cup_mug_glass_confusion",
    "table_desk_confusion",
    "textbook_workbook_confusion",
    "lunchbox_recordbook_confusion",
    "pencil_sharpener_confusion",
    "multiword_order_confusion",
    "compound_spacing_form_confusion",
    "source_normalization_confusion",
    "emoji_or_icon_ambiguity",
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
    AtomicSkill("G5-ENG-OBJECT-VOCAB-01", "object_pop", "භාවිත කරන දේවල් හඳුනාගැනීම", "easy", "object_vocabulary_mapping"),
    AtomicSkill("G5-ENG-OBJECT-PLACE-02", "two_room_tidy", "පාඩමේ ස්ථාන අනුව වචන වෙන් කිරීම", "medium", "lesson_place_sort"),
    AtomicSkill("G5-ENG-OBJECT-NAME-03", "name_builder", "වචන කිහිපයක නම් ගොඩනැගීම", "medium-hard", "object_name_sequence"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class EverydayObjectItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> EverydayObjectItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("EVERYDAY_OBJECT_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    if skill.chapter == "object_pop":
        rows = list(OBJECTS)
        rng.shuffle(rows)
        rows = rows[:4]
        words = [{"word_token": _token("w", key, salt), "text_en": text} for key, text, _, _ in rows]
        objects = [{"object_token": _token("o", key, salt), "renderer_variant": variant} for key, _, variant, _ in reversed(rows)]
        answer = {_token("w", key, salt): _token("o", key, salt) for key, _, _, _ in rows}
        game: dict[str, object] = {"response_kind": "object_vocabulary_mapping", "activity_id": skill.chapter, "command_token": command_token, "words": words, "objects": objects, "target_mapping": answer}
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන දේට සම්බන්ධ කරන්න."
    elif skill.chapter == "two_room_tidy":
        rows = list(OBJECTS)
        rng.shuffle(rows)
        classroom = [row for row in rows if row[3] == "classroom"][:3]
        home = [row for row in rows if row[3] == "home"][:3]
        selected = classroom + home
        entries = [{"entry_token": _token("e", key, salt), "text_en": text, "renderer_variant": variant} for key, text, variant, _ in selected]
        zones = [{"zone_token": _token("z", name, salt), "display_en": label, "zone_variant": index} for index, (name, label) in enumerate((("classroom", "Classroom"), ("home", "Home")))]
        answer = {_token("e", key, salt): _token("z", place, salt) for key, _, _, place in selected}
        rng.shuffle(entries)
        game = {"response_kind": "lesson_place_sort", "activity_id": skill.chapter, "command_token": command_token, "entries": entries, "zones": zones, "target_mapping": answer}
        prompt = "මේ පාඩමේ එන ස්ථානයට වචනය තබන්න."
    else:
        key, chunks, variant = MULTIWORD_NAMES[seed % len(MULTIWORD_NAMES)]
        object_token = _token("o", key, salt)
        chunk_rows = [{"chunk_token": _token("c", f"{key}:{index}", salt), "text_en": chunk} for index, chunk in enumerate(chunks)]
        answer = [row["chunk_token"] for row in chunk_rows]
        rng.shuffle(chunk_rows)
        game = {"response_kind": "object_name_sequence", "activity_id": skill.chapter, "command_token": command_token, "object_token": object_token, "renderer_variant": variant, "chunks": chunk_rows, "target_sequence": answer}
        prompt = "දේවල ඉංග්‍රීසි නම නිවැරදි පිළිවෙළට ගොඩනගන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return EverydayObjectItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]


def public_game_data(item: EverydayObjectItem) -> dict[str, object]:
    hidden = {"target_mapping", "target_sequence"}
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key not in hidden}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {"command_token": str(game["command_token"]), "interaction_trace": ["server:correct"], "revisions": 0, "invalid_drop_count": 0, "tap_alternative_used": True}
    kind = str(game["response_kind"])
    if kind == "object_name_sequence":
        return {"kind": kind, **common, "object_token": str(game["object_token"]), "ordered_chunk_tokens": list(game["target_sequence"]), "unused_chunk_tokens": []}
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    source_key = "word_token" if kind == "object_vocabulary_mapping" else "entry_token"
    target_key = "object_token" if kind == "object_vocabulary_mapping" else "zone_token"
    empty_key = "unplaced_word_tokens" if kind == "object_vocabulary_mapping" else "unplaced_entry_tokens"
    return {"kind": kind, **common, "placements": [{"sequence": index + 1, source_key: source, target_key: target} for index, (source, target) in enumerate(mapping.items())], empty_key: []}


def validate_constructed_response(item: Mapping[str, object] | EverydayObjectItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, EverydayObjectItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_EVERYDAY_OBJECT_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != game["response_kind"]:
        raise ValueError("MALFORMED_EVERYDAY_OBJECT_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_EVERYDAY_OBJECT_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_EVERYDAY_OBJECT_TRACE")
    kind = str(game["response_kind"])
    if kind == "object_name_sequence":
        submitted = response["ordered_chunk_tokens"]
        if not isinstance(submitted, list) or response["unused_chunk_tokens"] != [] or response["object_token"] != game["object_token"]:
            raise ValueError("INCOMPLETE_OBJECT_NAME_SEQUENCE")
        correct = submitted == game["target_sequence"]
        error = "multiword_order_confusion"
    else:
        rows = response["placements"]
        empty_key = "unplaced_word_tokens" if kind == "object_vocabulary_mapping" else "unplaced_entry_tokens"
        source_key = "word_token" if kind == "object_vocabulary_mapping" else "entry_token"
        target_key = "object_token" if kind == "object_vocabulary_mapping" else "zone_token"
        if not isinstance(rows, list) or response[empty_key] != []:
            raise ValueError("INCOMPLETE_EVERYDAY_OBJECT_MAPPING")
        submitted = {str(row[source_key]): str(row[target_key]) for row in rows if isinstance(row, Mapping)}
        answer = game["target_mapping"]
        assert isinstance(answer, Mapping)
        if len(submitted) != len(rows) or set(submitted) != set(answer):
            raise ValueError("INCOMPLETE_OR_DUPLICATE_OBJECT_MAPPING")
        correct = submitted == answer
        error = "object_word_visual_confusion" if kind == "object_vocabulary_mapping" else "classroom_home_lesson_heading_confusion"
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
        return ["දේවල හැඩය, පාඩමේ ස්ථානය හෝ නමේ හිස්තැන් හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "නව දේ හෝ ස්ථානය සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් වචනයක් තෝරන්න.", "රූප සංකේතය, ස්ථානය හෝ පිළිවෙළ බලන්න.", "නිවැරදි තැනට තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "skills": list(SKILLS), "objects": [row[0] for row in OBJECTS]}, sort_keys=True).encode()).hexdigest()
