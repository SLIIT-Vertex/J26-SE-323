"""Development Theme 7 clothes-vocabulary package for G5-AREA-ENG-07."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-07"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-rainbow-wardrobe-draft-v1"
CATALOGUE_VERSION = "g5-eng-clothes-misconceptions-v1"
FEATURE_VERSION = "g5-eng-clothes-features-v1"
MAPPING_VERSION = "g5-eng-clothes-source-mapping-v1"
MODEL_VERSION = "g5-eng-clothes-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-clothes-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-clothes-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-clothes-parallel-v1"

Chapter = Literal["rainbow_wardrobe"]
Role = Literal["unsupported_before", "unsupported_after"]

# Opaque renderer variants are intentionally separate from server-only semantic keys.
CLOTHES = (
    ("shoes", "Shoes", 0),
    ("socks", "Socks", 1),
    ("frock", "Frock", 2),
    ("shorts", "Shorts", 3),
    ("shirt", "Shirt", 4),
    ("trousers", "Trousers", 5),
    ("sarong", "Sarong", 6),
    ("saree", "Saree", 7),
    ("blouse", "Blouse", 8),
    ("skirt", "Skirt", 9),
)
# Handkerchief stays in immutable transcription but out of scored visual content
# until the cloth/tissue renderer distinction passes review.
EXCLUDED_PENDING_REVIEW = ("Handkerchief",)
STAGES = ("closet_flip", "laundry_line_relay", "style_detective")
MISCONCEPTIONS = (
    "clothes_word_visual_confusion",
    "shirt_blouse_confusion",
    "shorts_trousers_confusion",
    "shoes_socks_confusion",
    "frock_skirt_confusion",
    "sarong_saree_confusion",
    "handkerchief_generic_cloth_confusion",
    "printed_plural_form_confusion",
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
    AtomicSkill(
        "G5-ENG-CLOTHES-VOCAB-01",
        "rainbow_wardrobe",
        "ඇඳුම් සඳහා ඉංග්‍රීසි වචන හඳුනාගැනීම",
        "easy-to-hard",
        "clothes_vocabulary_mapping",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class RainbowWardrobeItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> RainbowWardrobeItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("RAINBOW_WARDROBE_ITEM_REQUEST_INVALID")
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    stage_index = seed % len(STAGES)
    stage = STAGES[stage_index]
    count = (3, 4, 4)[stage_index]
    rows = list(CLOTHES)
    rng.shuffle(rows)
    rows = rows[:count]
    words = [{"word_token": _token("w", key, salt), "text_en": text} for key, text, _ in rows]
    garments = [
        {"garment_token": _token("g", key, salt), "renderer_variant": variant}
        for key, _, variant in reversed(rows)
    ]
    answer = {_token("w", key, salt): _token("g", key, salt) for key, _, _ in rows}
    game = {
        "response_kind": "clothes_vocabulary_mapping",
        "activity_id": "rainbow_wardrobe",
        "stage": stage,
        "command_token": _token("cmd", "submit", salt),
        "words": words,
        "garments": garments,
        "target_mapping": answer,
    }
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return RainbowWardrobeItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:parallel-v1",
        skill_id,
        "rainbow_wardrobe",
        role,
        "ඉංග්‍රීසි වචනය ගැළපෙන ඇඳුමට සම්බන්ධ කරන්න.",
        (),
        "constructed-response",
        {},
        game,
    )


def public_game_data(item: RainbowWardrobeItem) -> dict[str, object]:
    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key != "target_mapping"},
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    return {
        "kind": "clothes_vocabulary_mapping",
        "command_token": str(game["command_token"]),
        "placements": [
            {"sequence": index + 1, "word_token": source, "garment_token": target}
            for index, (source, target) in enumerate(mapping.items())
        ],
        "unplaced_word_tokens": [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }


def validate_constructed_response(
    item: Mapping[str, object] | RainbowWardrobeItem,
    response: Mapping[str, object],
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, RainbowWardrobeItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_RAINBOW_WARDROBE_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != "clothes_vocabulary_mapping":
        raise ValueError("MALFORMED_RAINBOW_WARDROBE_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_RAINBOW_WARDROBE_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_RAINBOW_WARDROBE_TRACE")
    rows = response["placements"]
    if not isinstance(rows, list) or response["unplaced_word_tokens"] != []:
        raise ValueError("INCOMPLETE_CLOTHES_MAPPING")
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    allowed_targets = set(answer.values())
    if len(rows) != len(answer):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_CLOTHES_MAPPING")
    for index, row in enumerate(rows, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"sequence", "word_token", "garment_token"}
            or row["sequence"] != index
            or row["word_token"] not in answer
            or row["garment_token"] not in allowed_targets
        ):
            raise ValueError("INVALID_CLOTHES_MAPPING_TOKEN_OR_SEQUENCE")
    submitted = {str(row["word_token"]): str(row["garment_token"]) for row in rows}
    if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_CLOTHES_MAPPING")
    if not all(
        isinstance(response[key], int) and 0 <= response[key] <= 100
        for key in ("revisions", "invalid_drop_count")
    ) or not isinstance(response["tap_alternative_used"], bool):
        raise ValueError("INVALID_CLOTHES_INTERACTION_COUNTER")
    correct = submitted == answer
    error = "clothes_word_visual_confusion"
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
    del game
    if scaffold_type == "visual_guidance":
        return ["වචනය කියවා ඇඳුමේ හැඩය සහ දිග වැනි ලක්ෂණ බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව වචනය කියවමු.", "නව ඇඳුමේ හැඩය බලමු.", "දෙක සම්බන්ධ කර පරීක්ෂා කරමු."]
    return ["වචනයක් තෝරන්න.", "අත්, පාද හෝ හැඩයේ ලක්ෂණ සසඳන්න.", "ගැළපෙන ඇඳුමට තබා නැවත බලන්න."]


def package_hash() -> str:
    payload = {
        "area": AREA_ID,
        "version": PACKAGE_VERSION,
        "skills": list(SKILLS),
        "clothes": [row[0] for row in CLOTHES],
        "excluded": EXCLUDED_PENDING_REVIEW,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
