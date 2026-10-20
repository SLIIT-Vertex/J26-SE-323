"""Development-only Theme 10 flower vocabulary for G5-AREA-ENG-10."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-10"
PACKAGE_VERSION = "g5-eng-bloom-builder-draft-v1"
CATALOGUE_VERSION = "g5-eng-flower-misconceptions-v1"
FEATURE_VERSION = "g5-eng-flower-features-v1"
MAPPING_VERSION = "g5-eng-flower-source-mapping-v1"
MODEL_VERSION = "g5-eng-flower-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-flower-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-flower-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-flower-parallel-v1"

Chapter = Literal["seed_packet_match", "garden_bed_relay", "petal_pattern_detective"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, exact source English, opaque renderer variant. Shapes use more than colour.
FLOWERS = (
    ("marigold", "Marigold", 0),
    ("shoe_flower", "Shoe flower", 1),
    ("rose", "Rose", 2),
    ("sunflower", "Sunflower", 3),
    ("jasmine", "Jasmine", 4),
)
STAGES: tuple[tuple[Chapter, tuple[str, ...]], ...] = (
    ("seed_packet_match", ("rose", "sunflower", "jasmine")),
    ("garden_bed_relay", ("marigold", "rose", "sunflower", "jasmine")),
    ("petal_pattern_detective", ("marigold", "shoe_flower", "rose", "sunflower", "jasmine")),
)
MISCONCEPTIONS = (
    "flower_word_visual_confusion",
    "marigold_sunflower_confusion",
    "rose_shoe_flower_confusion",
    "jasmine_generic_blossom_confusion",
    "shoe_flower_source_term_confusion",
    "compound_spacing_form_confusion",
    "flower_structure_not_noticed",
    "colour_overreliance",
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
        "G5-ENG-FLOWER-VOCAB-01",
        "seed_packet_match",
        "මල් සඳහා ඉංග්‍රීසි නම් හඳුනාගැනීම",
        "easy-to-hard",
        "flower_vocabulary_mapping",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class BloomBuilderItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> BloomBuilderItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("BLOOM_BUILDER_ITEM_REQUEST_INVALID")
    chapter, keys = STAGES[seed % len(STAGES)]
    rows = [row for row in FLOWERS if row[0] in keys]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    words = [{"word_token": _token("w", key, salt), "text_en": text} for key, text, _ in rows]
    flowers = [{"flower_token": _token("f", key, salt), "renderer_variant": variant} for key, _, variant in rows]
    rng.shuffle(words)
    rng.shuffle(flowers)
    answer = {_token("w", key, salt): _token("f", key, salt) for key, _, _ in rows}
    game: dict[str, object] = {
        "response_kind": "flower_vocabulary_mapping",
        "activity_id": chapter,
        "command_token": _token("cmd", "submit", salt),
        "words": words,
        "flowers": flowers,
        "target_mapping": answer,
        "detail_sheet_enabled": chapter == "petal_pattern_detective",
    }
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return BloomBuilderItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:{chapter}:parallel-v1",
        skill_id,
        chapter,
        role,  # type: ignore[arg-type]
        "ඉංග්‍රීසි නම ගැළපෙන මලට සම්බන්ධ කරන්න.",
        (),
        "constructed-response",
        {},
        game,
    )


def public_game_data(item: BloomBuilderItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key != "target_mapping"}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    return {
        "kind": "flower_vocabulary_mapping",
        "command_token": str(game["command_token"]),
        "placements": [
            {"sequence": index + 1, "word_token": source, "flower_token": target}
            for index, (source, target) in enumerate(mapping.items())
        ],
        "unplaced_word_tokens": [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
        "detail_sheet_open_count": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | BloomBuilderItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, BloomBuilderItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_BLOOM_BUILDER_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != "flower_vocabulary_mapping":
        raise ValueError("MALFORMED_BLOOM_BUILDER_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_BLOOM_BUILDER_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_BLOOM_BUILDER_TRACE")
    rows = response["placements"]
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    if not isinstance(rows, list) or response["unplaced_word_tokens"] != [] or len(rows) != len(answer):
        raise ValueError("INCOMPLETE_FLOWER_MAPPING")
    allowed_targets = set(answer.values())
    for index, row in enumerate(rows, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"sequence", "word_token", "flower_token"}
            or row["sequence"] != index
            or row["word_token"] not in answer
            or row["flower_token"] not in allowed_targets
        ):
            raise ValueError("INVALID_FLOWER_MAPPING_TOKEN_OR_SEQUENCE")
    submitted = {str(row["word_token"]): str(row["flower_token"]) for row in rows}
    if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_FLOWER_MAPPING")
    for key in ("revisions", "invalid_drop_count", "detail_sheet_open_count"):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100:
            raise ValueError("INVALID_FLOWER_INTERACTION_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_FLOWER_INTERACTION_COUNTER")
    correct = submitted == answer
    return correct, "correct" if correct else "flower_word_visual_confusion", dict(response)


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
        return ["පාට පමණක් නොව පෙති, මැද කොටස සහ මල් පොකුරේ හැඩය බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි නම කියවමු.", "මලේ ව්‍යුහ ලක්ෂණ දෙකක් බලමු.", "නම සහ මල සම්බන්ධ කර පරීක්ෂා කරමු."]
    return ["නමක් තෝරන්න.", "පෙති සහ මැද කොටස සසඳන්න.", "ගැළපෙන මලට තබා නැවත බලන්න."]


def package_hash() -> str:
    payload = {"area": AREA_ID, "version": PACKAGE_VERSION, "flowers": [row[1] for row in FLOWERS]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
