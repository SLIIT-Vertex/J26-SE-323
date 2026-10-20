"""Development-only Theme 9 transport vocabulary for G5-AREA-ENG-09.

Scored probes use vehicles with distinct emoji. Closer contrasts whose
platform glyphs are still ambiguous stay in the transcription only.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-09"
PACKAGE_VERSION = "g5-eng-transit-terminal-draft-v1"
CATALOGUE_VERSION = "g5-eng-transport-misconceptions-v1"
FEATURE_VERSION = "g5-eng-transport-features-v1"
MAPPING_VERSION = "g5-eng-transport-source-mapping-v1"
MODEL_VERSION = "g5-eng-transport-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-transport-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-transport-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-transport-parallel-v1"

Chapter = Literal["ticket_match", "departure_board", "signal_detective"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, exact source English, renderer variant. Distinct glyphs only.
VEHICLES = (
    ("train", "Train", 0),
    ("bicycle", "Bicycle", 1),
    ("helicopter", "Helicopter", 2),
    ("aeroplane", "Aeroplane", 3),
    ("bus", "Bus", 4),
    ("car", "Car", 5),
)
EXCLUDED_UNTIL_RENDERER_REVIEW = ("Lorry", "Van", "Ship", "Boat", "Cart")
STAGES: tuple[tuple[Chapter, tuple[str, ...]], ...] = (
    ("ticket_match", ("train", "bicycle", "helicopter")),
    ("departure_board", ("train", "aeroplane", "bus", "car")),
    ("signal_detective", ("aeroplane", "helicopter", "bus", "car", "bicycle")),
)
MISCONCEPTIONS = (
    "transport_word_visual_confusion",
    "lorry_van_bus_car_confusion",
    "ship_boat_confusion",
    "aeroplane_helicopter_confusion",
    "bicycle_cart_confusion",
    "regional_transport_word_confusion",
    "vehicle_detail_not_noticed",
    "emoji_or_code_glyph_ambiguity",
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
    AtomicSkill("G5-ENG-TRANSPORT-VOCAB-01", "ticket_match", "ප්‍රවාහන වචන හඳුනාගැනීම", "easy-to-hard", "transport_vocabulary_mapping"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class TransitTerminalItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> TransitTerminalItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("TRANSIT_TERMINAL_ITEM_REQUEST_INVALID")
    chapter, keys = STAGES[seed % len(STAGES)]
    rows = [row for row in VEHICLES if row[0] in keys]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    words = [{"word_token": _token("w", key, salt), "text_en": text} for key, text, _ in rows]
    vehicles = [{"vehicle_token": _token("v", key, salt), "renderer_variant": variant} for key, _, variant in reversed(rows)]
    rng.shuffle(words)
    rng.shuffle(vehicles)
    answer = {_token("w", key, salt): _token("v", key, salt) for key, _, _ in rows}
    game: dict[str, object] = {
        "response_kind": "transport_vocabulary_mapping",
        "activity_id": chapter,
        "command_token": command_token,
        "words": words,
        "vehicles": vehicles,
        "target_mapping": answer,
    }
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    prompt = "ඉංග්‍රීසි වචනය ගැළපෙන වාහනයට සම්බන්ධ කරන්න."
    return TransitTerminalItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]


def public_game_data(item: TransitTerminalItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key != "target_mapping"}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    return {
        "kind": "transport_vocabulary_mapping",
        "command_token": str(game["command_token"]),
        "placements": [{"sequence": index + 1, "word_token": source, "vehicle_token": target} for index, (source, target) in enumerate(mapping.items())],
        "unplaced_word_tokens": [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }


def validate_constructed_response(item: Mapping[str, object] | TransitTerminalItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, TransitTerminalItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_TRANSIT_TERMINAL_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != "transport_vocabulary_mapping":
        raise ValueError("MALFORMED_TRANSIT_TERMINAL_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_TRANSIT_TERMINAL_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_TRANSIT_TERMINAL_TRACE")
    rows = response["placements"]
    if not isinstance(rows, list) or response["unplaced_word_tokens"] != []:
        raise ValueError("INCOMPLETE_TRANSPORT_MAPPING")
    submitted = {str(row["word_token"]): str(row["vehicle_token"]) for row in rows if isinstance(row, Mapping)}
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    if len(submitted) != len(rows) or set(submitted) != set(answer) or len(set(submitted.values())) != len(submitted):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_TRANSPORT_MAPPING")
    correct = submitted == answer
    return correct, "correct" if correct else "transport_word_visual_confusion", dict(response)


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
        return ["වාහනයේ රෝද, පියාපත් හෝ කවුළු හොඳින් බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "නව වාහනය සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් ප්‍රවේශ පත්‍රයක් තෝරන්න.", "වාහන දෙකක් සසඳන්න.", "නිවැරදි වාහනයට තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "vehicles": [row[1] for row in VEHICLES], "excluded": list(EXCLUDED_UNTIL_RENDERER_REVIEW)}, sort_keys=True).encode()).hexdigest()
