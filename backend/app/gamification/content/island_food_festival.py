"""Development-only Theme 6 food vocabulary for G5-AREA-ENG-06.

Scored content uses reviewed source forms only. Unresolved forms stay in the
transcription and are excluded from generated items.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-06"
PACKAGE_VERSION = "g5-eng-island-food-festival-draft-v1"
CATALOGUE_VERSION = "g5-eng-food-misconceptions-v1"
FEATURE_VERSION = "g5-eng-food-features-v1"
MAPPING_VERSION = "g5-eng-food-source-mapping-v1"
MODEL_VERSION = "g5-eng-food-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-food-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-food-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-food-parallel-v1"

Chapter = Literal["market_match", "festival_stall_sort", "recipe_word_kitchen"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, source English, renderer variant, lesson heading, vocabulary-safe glyph
FOODS = (
    ("egg", "Egg", 0, "food", True),
    ("bread", "Bread", 1, "food", True),
    ("fish", "Fish", 2, "food", True),
    ("coconut", "Coconut", 3, "food", True),
    ("buns", "Buns", 4, "food", True),
    ("healthy-food", "Healthy Food", 5, "food", False),
    ("fatty-food", "Fatty Food", 6, "food", False),
    ("spicy-food", "Spicy Food", 7, "food", False),
    ("homemade-food", "Homemade Food", 8, "food", False),
    ("junk-food", "Junk Food", 9, "food", False),
    ("manioc", "Manioc", 10, "yams", False),
    ("sweet-potatoes", "Sweet Potatoes", 11, "yams", True),
    ("tea", "Tea", 12, "drinks", True),
    ("milk", "Milk", 13, "drinks", True),
    ("water", "Water", 14, "drinks", True),
    ("fruit-juice", "Fruit Juice", 15, "drinks", True),
    ("banana", "Banana", 16, "fruits", True),
    ("pineapple", "Pineapple", 17, "fruits", True),
    ("mango", "Mango", 18, "fruits", True),
    ("watermelon", "Watermelon", 19, "fruits", True),
    ("olive", "Olive", 20, "fruits", True),
    ("potato", "Potato", 21, "vegetables", True),
    ("cabbage", "Cabbage", 22, "vegetables", True),
    ("tomato", "Tomato", 23, "vegetables", True),
    ("carrot", "Carrot", 24, "vegetables", True),
    ("cucumber", "Cucumber", 25, "vegetables", True),
)
MULTIWORD_NAMES = (
    ("rice-and-curry", ("Rice", "and", "Curry"), 26),
    ("ice-cream", ("Ice", "Cream"), 27),
    ("sweet-potatoes-name", ("Sweet", "Potatoes"), 11),
    ("fruit-juice-name", ("Fruit", "Juice"), 15),
    ("rose-apple", ("Rose", "Apple"), 28),
    ("custard-apple", ("Custard", "Apple"), 29),
    ("beet-root", ("Beet", "root"), 30),
    ("curry-leaves", ("Curry", "Leaves"), 31),
)
UNRESOLVED_SOURCE_FORMS = (
    "Jak",
    "Drumsticks",
    "Hoppers",
    "String Hoppers",
    "Pawpaw / Papaya",
    "Woodapple",
)
MISCONCEPTIONS = (
    "food_word_visual_confusion",
    "fruit_vegetable_lesson_heading_confusion",
    "food_drink_lesson_heading_confusion",
    "yam_vegetable_lesson_heading_confusion",
    "mango_papaya_pineapple_confusion",
    "water_milk_fruit_juice_confusion",
    "potato_sweet_potatoes_confusion",
    "hoppers_string_hoppers_confusion",
    "rose_apple_custard_apple_confusion",
    "multiword_order_confusion",
    "source_variant_or_spacing_confusion",
    "emoji_or_code_glyph_ambiguity",
    "incomplete_mapping_or_omission",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
HEADINGS = (("food", "Food"), ("yams", "Yams"), ("drinks", "Drinks"), ("fruits", "Fruits"), ("vegetables", "Vegetables"))


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-ENG-FOOD-VOCAB-01", "market_match", "ආහාර වචන හඳුනාගැනීම", "easy", "food_vocabulary_mapping"),
    AtomicSkill("G5-ENG-FOOD-GROUP-02", "festival_stall_sort", "පාඩමේ තැන් අනුව ආහාර වෙන් කිරීම", "medium", "food_lesson_group_sort"),
    AtomicSkill("G5-ENG-FOOD-NAME-03", "recipe_word_kitchen", "වචන කිහිපයක ආහාර නම්", "medium-hard", "food_name_sequence"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class IslandFoodItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> IslandFoodItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("ISLAND_FOOD_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    if skill.chapter == "market_match":
        rows = [row for row in FOODS if row[4]]
        rng.shuffle(rows)
        rows = rows[:4]
        words = [{"word_token": _token("w", key, salt), "text_en": text} for key, text, _, _, _ in rows]
        foods = [{"food_token": _token("f", key, salt), "renderer_variant": variant} for key, _, variant, _, _ in reversed(rows)]
        answer = {_token("w", key, salt): _token("f", key, salt) for key, _, _, _, _ in rows}
        game: dict[str, object] = {"response_kind": "food_vocabulary_mapping", "activity_id": skill.chapter, "command_token": command_token, "words": words, "foods": foods, "target_mapping": answer}
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන ආහාරයට සම්බන්ධ කරන්න."
    elif skill.chapter == "festival_stall_sort":
        by_heading: dict[str, list[tuple[str, str, int, str, bool]]] = {name: [] for name, _ in HEADINGS}
        for row in FOODS:
            by_heading[row[3]].append(row)
        selected: list[tuple[str, str, int, str, bool]] = []
        for heading, _label in HEADINGS:
            pool = list(by_heading[heading])
            rng.shuffle(pool)
            selected.extend(pool[:1])
        entries = [{"entry_token": _token("e", key, salt), "text_en": text} for key, text, _, _, _ in selected]
        stalls = [{"stall_token": _token("s", name, salt), "display_en": label, "stall_variant": index} for index, (name, label) in enumerate(HEADINGS)]
        answer = {_token("e", key, salt): _token("s", heading, salt) for key, _, _, heading, _ in selected}
        rng.shuffle(entries)
        game = {"response_kind": "food_lesson_group_sort", "activity_id": skill.chapter, "command_token": command_token, "entries": entries, "stalls": stalls, "target_mapping": answer}
        prompt = "මේ පාඩමේ එන තැනට වචනය තබන්න."
    else:
        key, chunks, variant = MULTIWORD_NAMES[seed % len(MULTIWORD_NAMES)]
        food_token = _token("f", key, salt)
        chunk_rows = [{"chunk_token": _token("c", f"{key}:{index}", salt), "text_en": chunk} for index, chunk in enumerate(chunks)]
        answer = [row["chunk_token"] for row in chunk_rows]
        rng.shuffle(chunk_rows)
        game = {"response_kind": "food_name_sequence", "activity_id": skill.chapter, "command_token": command_token, "food_token": food_token, "renderer_variant": variant, "chunks": chunk_rows, "target_sequence": answer}
        prompt = "ආහාරයේ ඉංග්‍රීසි නම නිවැරදි පිළිවෙළට ගොඩනගන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return IslandFoodItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]


def public_game_data(item: IslandFoodItem) -> dict[str, object]:
    hidden = {"target_mapping", "target_sequence"}
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key not in hidden}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {"command_token": str(game["command_token"]), "interaction_trace": ["server:correct"], "revisions": 0, "invalid_drop_count": 0, "tap_alternative_used": True}
    kind = str(game["response_kind"])
    if kind == "food_name_sequence":
        return {"kind": kind, **common, "food_token": str(game["food_token"]), "ordered_chunk_tokens": list(game["target_sequence"]), "unused_chunk_tokens": []}
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    source_key = "word_token" if kind == "food_vocabulary_mapping" else "entry_token"
    target_key = "food_token" if kind == "food_vocabulary_mapping" else "stall_token"
    empty_key = "unplaced_word_tokens" if kind == "food_vocabulary_mapping" else "unplaced_entry_tokens"
    return {"kind": kind, **common, "placements": [{"sequence": index + 1, source_key: source, target_key: target} for index, (source, target) in enumerate(mapping.items())], empty_key: []}


def validate_constructed_response(item: Mapping[str, object] | IslandFoodItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, IslandFoodItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_ISLAND_FOOD_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != game["response_kind"]:
        raise ValueError("MALFORMED_ISLAND_FOOD_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_ISLAND_FOOD_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_ISLAND_FOOD_TRACE")
    kind = str(game["response_kind"])
    if kind == "food_name_sequence":
        submitted = response["ordered_chunk_tokens"]
        if not isinstance(submitted, list) or response["unused_chunk_tokens"] != [] or response["food_token"] != game["food_token"]:
            raise ValueError("INCOMPLETE_FOOD_NAME_SEQUENCE")
        correct = submitted == game["target_sequence"]
        error = "multiword_order_confusion"
    else:
        rows = response["placements"]
        empty_key = "unplaced_word_tokens" if kind == "food_vocabulary_mapping" else "unplaced_entry_tokens"
        source_key = "word_token" if kind == "food_vocabulary_mapping" else "entry_token"
        target_key = "food_token" if kind == "food_vocabulary_mapping" else "stall_token"
        if not isinstance(rows, list) or response[empty_key] != []:
            raise ValueError("INCOMPLETE_ISLAND_FOOD_MAPPING")
        submitted = {str(row[source_key]): str(row[target_key]) for row in rows if isinstance(row, Mapping)}
        answer = game["target_mapping"]
        assert isinstance(answer, Mapping)
        if len(submitted) != len(rows) or set(submitted) != set(answer):
            raise ValueError("INCOMPLETE_OR_DUPLICATE_FOOD_MAPPING")
        correct = submitted == answer
        error = "food_word_visual_confusion" if kind == "food_vocabulary_mapping" else "fruit_vegetable_lesson_heading_confusion"
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
        return ["ආහාරයේ හැඩය, පාඩමේ තැන හෝ නමේ හිස්තැන් හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "නව ආහාරය හෝ තැන සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් වචනයක් තෝරන්න.", "රූප සංකේතය, තැන හෝ පිළිවෙළ බලන්න.", "නිවැරදි තැනට තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "skills": list(SKILLS), "foods": [row[0] for row in FOODS], "unresolved": list(UNRESOLVED_SOURCE_FORMS)}, sort_keys=True).encode()).hexdigest()
