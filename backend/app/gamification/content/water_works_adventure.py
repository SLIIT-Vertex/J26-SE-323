"""Development-only Theme 8 water-action vocabulary for G5-AREA-ENG-08."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.gamification.content.simpler_items import simpler_matching_item

AREA_ID = "G5-AREA-ENG-08"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-water-works-draft-v1"
CATALOGUE_VERSION = "g5-eng-water-misconceptions-v1"
FEATURE_VERSION = "g5-eng-water-features-v1"
MAPPING_VERSION = "g5-eng-water-source-mapping-v1"
MODEL_VERSION = "g5-eng-water-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-water-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-water-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-water-parallel-v1"

Chapter = Literal["droplet_match", "pipe_route", "splash_detective"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, exact source English, renderer variant
ACTIONS = (
    ("bathe", "Bathe", 0),
    ("cook", "Cook", 1),
    ("wash", "Wash", 2),
    ("drink", "Drink", 3),
    ("water-plants", "Water (the plants)", 4),
)
STAGES: tuple[tuple[Chapter, int, tuple[str, ...]], ...] = (
    ("droplet_match", 2, ("drink", "water-plants")),
    ("pipe_route", 3, ("drink", "cook", "water-plants")),
    ("splash_detective", 5, ("bathe", "cook", "wash", "drink", "water-plants")),
)
MISCONCEPTIONS = (
    "water_action_scene_confusion",
    "bathe_wash_confusion",
    "drink_wash_confusion",
    "cook_wash_confusion",
    "drink_water_plants_confusion",
    "water_noun_verb_context_confusion",
    "parenthetical_context_cue_confusion",
    "scene_detail_not_noticed",
    "emoji_or_code_scene_ambiguity",
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
    AtomicSkill("G5-ENG-WATER-ACTION-01", "droplet_match", "ජලය භාවිත ක්‍රියා හඳුනාගැනීම", "easy-to-hard", "water_action_mapping"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class WaterWorksItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> WaterWorksItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("WATER_WORKS_ITEM_REQUEST_INVALID")
    chapter, _count, keys = STAGES[seed % len(STAGES)]
    rows = [row for row in ACTIONS if row[0] in keys]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    words = [{"action_token": _token("a", key, salt), "text_en": text} for key, text, _ in rows]
    scenes = [{"scene_token": _token("s", key, salt), "renderer_variant": variant} for key, _, variant in reversed(rows)]
    rng.shuffle(words)
    rng.shuffle(scenes)
    answer = {_token("a", key, salt): _token("s", key, salt) for key, _, _ in rows}
    game: dict[str, object] = {
        "response_kind": "water_action_mapping",
        "activity_id": chapter,
        "command_token": command_token,
        "actions": words,
        "scenes": scenes,
        "target_mapping": answer,
    }
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    prompt = "ඉංග්‍රීසි ක්‍රියාව ගැළපෙන ජල දර්ශනයට සම්බන්ධ කරන්න."
    return WaterWorksItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]

def generate_simpler_item(skill_id: str, *, seed: int, than: Mapping[str, object]) -> WaterWorksItem | None:
    """The same game and skill with fewer pairs to link than the failed game, from a fresh item."""

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    return simpler_matching_item(item, than=than)



def public_game_data(item: WaterWorksItem) -> dict[str, object]:
    hidden = {"target_mapping"}
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key not in hidden}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    return {
        "kind": "water_action_mapping",
        "command_token": str(game["command_token"]),
        "placements": [{"sequence": index + 1, "action_token": source, "scene_token": target} for index, (source, target) in enumerate(mapping.items())],
        "unplaced_action_tokens": [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }


def validate_constructed_response(item: Mapping[str, object] | WaterWorksItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, WaterWorksItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_WATER_WORKS_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != "water_action_mapping":
        raise ValueError("MALFORMED_WATER_WORKS_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_WATER_WORKS_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_WATER_WORKS_TRACE")
    rows = response["placements"]
    if not isinstance(rows, list) or response["unplaced_action_tokens"] != []:
        raise ValueError("INCOMPLETE_WATER_ACTION_MAPPING")
    submitted = {str(row["action_token"]): str(row["scene_token"]) for row in rows if isinstance(row, Mapping)}
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    if len(submitted) != len(rows) or set(submitted) != set(answer) or len(set(submitted.values())) != len(submitted):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_WATER_MAPPING")
    correct = submitted == answer
    return correct, "correct" if correct else "water_action_scene_confusion", dict(response)


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
        return ["දර්ශනයේ ජලය යන තැන හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි ක්‍රියාව කියවමු.", "නව දර්ශනය සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් වචනයක් තෝරන්න.", "දර්ශන දෙකක් සසඳන්න.", "නිවැරදි දර්ශනයට තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "actions": [row[1] for row in ACTIONS]}, sort_keys=True).encode()).hexdigest()
