"""Development-only Theme 14 School & Home Blueprint Quest content."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-14"
PACKAGE_VERSION = "g5-eng-blueprint-quest-draft-v1"
CATALOGUE_VERSION = "g5-eng-blueprint-misconceptions-v1"
FEATURE_VERSION = "g5-eng-blueprint-features-v1"
MAPPING_VERSION = "g5-eng-blueprint-source-mapping-v1"
MODEL_VERSION = "g5-eng-blueprint-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-blueprint-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-blueprint-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-blueprint-parallel-v1"

Chapter = Literal["place_card_explorer", "blueprint_zone_sort", "room_name_workshop"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, exact English, exact Sinhala, source heading, renderer variant
SOURCE_ENTRIES = (
    ("laboratory", "Laboratory", "විද්‍යාගාරය", "school", 0),
    ("shrine_room", "Shrine room", "බුදු මැදුර", "school", None),
    ("staff_room", "Staff room", "ගුරු විවේකාගාරය", "school", 1),
    ("sick_room", "Sick room", "ගිලන් කාමරය", "school", None),
    ("library", "Library", "පුස්තකාලය", "school", 2),
    ("computer_room", "Computer room", "පරිගණක කාමරය", "school", 3),
    ("classroom", "Classroom", "පන්ති කාමරය", "school", 4),
    ("toilet", "Toilet", "වැසිකිළිය", "school", None),
    ("canteen", "Canteen", "ආපනශාලාව", "school", 5),
    ("office", "Office", "කාර්යාලය", "school", 6),
    ("playground", "Playground", "ක්‍රීඩා පිටිය", "school", 7),
    ("door", "Door", "දොර", "parts", 8), ("window", "Window", "ජනේලය", "parts", 9),
    ("roof", "Roof", "වහලය", "parts", 10), ("wall", "Wall", "බිත්තිය", "parts", 11),
    ("kitchen", "Kitchen", "කුස්සිය", "rooms", 12), ("living_room", "Living Room", "සාලය", "rooms", 13),
    ("bathroom", "Bathroom", "නාන කාමරය", "rooms", 14), ("bedroom", "Bedroom", "නිදන කාමරය", "rooms", 15),
    ("store_room", "Store room", "ගබඩා කාමරය", "rooms", 16),
)
HEADINGS = (("school", "Places in the School"), ("parts", "Parts of a House"), ("rooms", "Rooms of a House"))
BLOCKED_TERMS = ("Shrine room", "Sick room")
PHRASE_FORMS = ("Staff room", "Computer room", "Living Room", "Store room")
MISCONCEPTIONS = (
    "place_word_visual_confusion", "school_place_house_place_confusion", "house_part_house_room_confusion",
    "classroom_staff_room_office_confusion", "laboratory_computer_room_confusion", "sick_room_bedroom_confusion",
    "library_classroom_confusion", "door_window_wall_roof_confusion", "living_room_store_room_confusion",
    "multiword_room_name_confusion", "source_spacing_or_capitalization_confusion",
    "lesson_heading_exclusivity_assumption", "emoji_or_code_scene_ambiguity",
    "incomplete_mapping_or_omission", "unknown_or_other",
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
    AtomicSkill("G5-ENG-PLACE-VOCAB-01", "place_card_explorer", "ස්ථාන සහ ගෘහ කොටස් වචන හඳුනාගැනීම", "easy-to-hard", "place_vocabulary_mapping"),
    AtomicSkill("G5-ENG-PLACE-GROUP-02", "blueprint_zone_sort", "පාඩමේ ශීර්ෂ යටතේ වචන තැබීම", "easy-to-hard", "lesson_place_group_sort"),
    AtomicSkill("G5-ENG-PLACE-NAME-03", "room_name_workshop", "බහුපද ස්ථාන නාම ගොඩනැගීම", "easy-to-hard", "place_name_sequence"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class BlueprintItem:
    item_id: str; revision_id: str; parallel_family_id: str; skill_id: str; chapter: Chapter
    measurement_role: Role; prompt_si: str; options: tuple[tuple[str, str], ...]
    correct_option_id: str; error_codes: dict[str, str]; game_data: dict[str, object]


def _token(prefix: str, value: str, salt: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def generate_item(skill_id: str, *, role: str, seed: int) -> BlueprintItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("BLUEPRINT_ITEM_REQUEST_INVALID")
    rng = random.Random(int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big"))
    salt = f"{skill_id}:{role}:{seed}"
    if skill_id == "G5-ENG-PLACE-VOCAB-01":
        eligible = [row for row in SOURCE_ENTRIES if row[4] is not None and row[1] not in BLOCKED_TERMS]
        rng.shuffle(eligible); rows = eligible[: (3 if seed % 2 == 0 else 4)]
        words = [{"word_token": _token("w", row[0], salt), "text_en": row[1]} for row in rows]
        scenes = [{"scene_token": _token("c", row[0], salt), "renderer_variant": row[4]} for row in reversed(rows)]
        game = {"response_kind": "place_vocabulary_mapping", "activity_id": "place_card_explorer", "command_token": _token("cmd", "scene", salt), "words": words, "scenes": scenes, "target_mapping": {_token("w", row[0], salt): _token("c", row[0], salt) for row in rows}}
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන සැලසුම් කාඩ්පතට තබන්න."
    elif skill_id == "G5-ENG-PLACE-GROUP-02":
        heading_rows = list(HEADINGS if seed % 2 else HEADINGS[:2])
        rows: list[tuple[str, str, str, str, int | None]] = []
        for key, _ in heading_rows:
            candidates = [row for row in SOURCE_ENTRIES if row[3] == key and row[1] not in BLOCKED_TERMS]
            rng.shuffle(candidates); rows.extend(candidates[:2])
        entries = [{"entry_token": _token("e", row[0], salt), "text_en": row[1]} for row in rows]
        headings = [{"heading_token": _token("h", key, salt), "text_en": text, "capacity": sum(row[3] == key for row in rows)} for key, text in heading_rows]
        rng.shuffle(entries); rng.shuffle(headings)
        game = {"response_kind": "lesson_place_group_sort", "activity_id": "blueprint_zone_sort", "command_token": _token("cmd", "sort", salt), "entries": entries, "headings": headings, "target_mapping": {_token("e", row[0], salt): _token("h", row[3], salt) for row in rows}}
        prompt = "මෙම පාඩමේ පෙනෙන ශීර්ෂය යටතේ එක් එක් වචනය තබන්න."
    else:
        forms = [row for row in SOURCE_ENTRIES if row[1] in PHRASE_FORMS]
        row = forms[seed % len(forms)]
        chunks = row[1].split(" ")
        chunk_rows = [{"chunk_token": _token("k", f"{row[0]}:{index}", salt), "text_en": text} for index, text in enumerate(chunks)]
        rng.shuffle(chunk_rows)
        game = {"response_kind": "place_name_sequence", "activity_id": "room_name_workshop", "command_token": _token("cmd", "sequence", salt), "place_token": _token("p", row[0], salt), "renderer_variant": row[4], "chunks": chunk_rows, "slot_count": len(chunks), "target_sequence": [_token("k", f"{row[0]}:{index}", salt) for index in range(len(chunks))]}
        prompt = "පාඩමේ බහුපද ස්ථාන නාමය සෑදීමට සම්පූර්ණ වචන පිළිවෙළට තබන්න."
    chapter = SKILLS[skill_id].chapter
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return BlueprintItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)


def public_game_data(item: BlueprintItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key not in {"target_mapping", "target_sequence"}}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {"command_token": str(game["command_token"]), "interaction_trace": ["server:correct"], "revisions": 0, "invalid_drop_count": 0, "tap_alternative_used": True}
    if game["response_kind"] == "place_name_sequence":
        sequence = game["target_sequence"]; assert isinstance(sequence, list)
        return {"kind": "place_name_sequence", **common, "place_token": str(game["place_token"]), "ordered_chunk_tokens": list(sequence), "unused_chunk_tokens": []}
    mapping = game["target_mapping"]; assert isinstance(mapping, Mapping)
    if game["response_kind"] == "place_vocabulary_mapping":
        return {"kind": "place_vocabulary_mapping", **common, "placements": [{"sequence": i + 1, "word_token": source, "scene_token": target} for i, (source, target) in enumerate(mapping.items())], "unplaced_word_tokens": []}
    return {"kind": "lesson_place_group_sort", **common, "placements": [{"sequence": i + 1, "entry_token": source, "heading_token": target} for i, (source, target) in enumerate(mapping.items())], "unplaced_entry_tokens": []}


def validate_constructed_response(item: Mapping[str, object] | BlueprintItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, BlueprintItem) else item["game_data"]
    if not isinstance(game, Mapping): raise TypeError("MALFORMED_BLUEPRINT_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]: raise ValueError("MALFORMED_BLUEPRINT_RESPONSE")
    if response.get("command_token") != game["command_token"]: raise ValueError("STALE_BLUEPRINT_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace): raise ValueError("INVALID_BLUEPRINT_TRACE")
    for key in ("revisions", "invalid_drop_count"):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100: raise ValueError("INVALID_BLUEPRINT_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool): raise TypeError("INVALID_BLUEPRINT_COUNTER")
    if response["kind"] == "place_name_sequence":
        allowed = game["target_sequence"]; submitted = response["ordered_chunk_tokens"]
        if response["place_token"] != game["place_token"] or response["unused_chunk_tokens"] != [] or not isinstance(allowed, list) or not isinstance(submitted, list) or len(submitted) != len(allowed) or len(set(submitted)) != len(submitted) or set(submitted) != set(allowed): raise ValueError("INVALID_BLUEPRINT_SEQUENCE")
        correct = submitted == allowed
        return correct, "correct" if correct else "multiword_room_name_confusion", dict(response)
    vocabulary = response["kind"] == "place_vocabulary_mapping"
    mapping = game["target_mapping"]; assert isinstance(mapping, Mapping)
    rows = response["placements"]; source_key = "word_token" if vocabulary else "entry_token"; target_key = "scene_token" if vocabulary else "heading_token"; empty_key = "unplaced_word_tokens" if vocabulary else "unplaced_entry_tokens"
    if not isinstance(rows, list) or response[empty_key] != [] or len(rows) != len(mapping): raise ValueError("INCOMPLETE_BLUEPRINT_RESPONSE")
    submitted_map: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping) or set(row) != {"sequence", source_key, target_key} or row["sequence"] != index or row[source_key] not in mapping or row[target_key] not in set(mapping.values()): raise ValueError("INVALID_BLUEPRINT_TOKEN_OR_SEQUENCE")
        submitted_map[str(row[source_key])] = str(row[target_key])
    if len(submitted_map) != len(rows) or (vocabulary and len(set(submitted_map.values())) != len(rows)): raise ValueError("DUPLICATE_BLUEPRINT_SOURCE_OR_TARGET")
    correct = submitted_map == mapping
    error = "place_word_visual_confusion" if vocabulary else "lesson_heading_exclusivity_assumption"
    return correct, "correct" if correct else error, dict(response)


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"; confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72)); remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1); probabilities = {key: confidence if key == primary else remainder for key in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if scaffold_type == "visual_guidance": return ["වචනය සහ කාඩ්පත් හෝ ශීර්ෂ වෙන වෙනම සසඳන්න."]
    if scaffold_type == "worked_parallel_example": return ["නව වචනයක් කියවමු.", "නව ඉලක්ක සසඳමු.", "නව පිළිතුර සකස් කරමු."]
    return ["එක් සම්පූර්ණ වචනයක් තෝරන්න.", "පාඩමේ දර්ශනය, ශීර්ෂය හෝ පද පිළිවෙළ සසඳන්න.", "පිළිතුර තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "source": [(row[1], row[2], row[3]) for row in SOURCE_ENTRIES], "blocked": BLOCKED_TERMS}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
