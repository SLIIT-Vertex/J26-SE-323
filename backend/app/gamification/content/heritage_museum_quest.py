"""Development-only Theme 16 Heritage Museum Quest content."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.gamification.content.simpler_items import shown_tokens, simpler_matching_item

AREA_ID = "G5-AREA-ENG-16"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-heritage-museum-draft-v1"
CATALOGUE_VERSION = "g5-eng-past-misconceptions-v1"
FEATURE_VERSION = "g5-eng-past-features-v1"
MAPPING_VERSION = "g5-eng-past-source-mapping-v1"
MODEL_VERSION = "g5-eng-past-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-past-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-past-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-past-parallel-v1"

Chapter = Literal["museum_word_bridge", "exhibit_label_match", "curator_lens_challenge"]
Role = Literal["unsupported_before", "unsupported_after"]

# Numeric renderer variants are deliberately opaque on the public contract.
SOURCE_PAIRS = (
    ("timber-carvings", "Timber carvings", "ලී කැටයම්", 0),
    ("stone-carvings", "Stone carvings", "ගල් කැටයම්", 1),
    ("palace", "Palace", "මාලිගාව", 2),
    ("throne", "Throne", "සිංහාසනය", 3),
    ("crown", "Crown", "ඔටුන්න", 4),
)
UNRESOLVED_RENDERERS: tuple[str, ...] = ()
MISCONCEPTIONS = (
    "english_sinhala_past_word_confusion",
    "heritage_word_exhibit_confusion",
    "timber_stone_carving_confusion",
    "palace_throne_confusion",
    "throne_ordinary_chair_confusion",
    "crown_generic_headpiece_confusion",
    "timber_wood_source_term_confusion",
    "source_plural_form_confusion",
    "material_texture_not_noticed",
    "cultural_or_code_exhibit_ambiguity",
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
        "G5-ENG-PAST-BILINGUAL-01",
        "museum_word_bridge",
        "අතීතය පිළිබඳ ඉංග්‍රීසි සහ සිංහල වචන සම්බන්ධ කිරීම",
        "easy-to-hard",
        "past_bilingual_links",
    ),
    AtomicSkill(
        "G5-ENG-PAST-VISUAL-02",
        "exhibit_label_match",
        "අනුමත වචන සහ සරල කේත ප්‍රදර්ශන සම්බන්ධ කිරීම",
        "easy-to-hard",
        "heritage_exhibit_mapping",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class HeritageItem:
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


def _token(prefix: str, value: str, salt: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def generate_item(skill_id: str, *, role: str, seed: int) -> HeritageItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("HERITAGE_ITEM_REQUEST_INVALID")
    rng = random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    )
    salt = f"{skill_id}:{role}:{seed}"
    rows = [row for row in SOURCE_PAIRS if row[1] not in UNRESOLVED_RENDERERS]
    rng.shuffle(rows)
    count = 2 if seed % 2 == 0 else min(5, len(rows))
    rows = rows[:count]
    if skill_id == "G5-ENG-PAST-BILINGUAL-01":
        english = [{"english_token": _token("e", row[0], salt), "text_en": row[1]} for row in rows]
        sinhala = [
            {"sinhala_token": _token("s", row[0], salt), "text_si": row[2]}
            for row in reversed(rows)
        ]
        game = {
            "response_kind": "past_bilingual_links",
            "activity_id": "museum_word_bridge",
            "command_token": _token("cmd", "bridge", salt),
            "english_words": english,
            "sinhala_words": sinhala,
            "target_mapping": {
                _token("e", row[0], salt): _token("s", row[0], salt) for row in rows
            },
        }
        chapter: Chapter = "museum_word_bridge"
        prompt = "ඉංග්‍රීසි ප්‍රදර්ශන වචනය ගැළපෙන සිංහල වචනයට සම්බන්ධ කරන්න."
    else:
        words = [{"word_token": _token("w", row[0], salt), "text_en": row[1]} for row in rows]
        exhibits = [
            {"exhibit_token": _token("x", row[0], salt), "renderer_variant": row[3]}
            for row in reversed(rows)
        ]
        game = {
            "response_kind": "heritage_exhibit_mapping",
            "activity_id": "curator_lens_challenge" if count > 2 else "exhibit_label_match",
            "command_token": _token("cmd", "exhibit", salt),
            "words": words,
            "exhibits": exhibits,
            "target_mapping": {
                _token("w", row[0], salt): _token("x", row[0], salt) for row in rows
            },
        }
        chapter = "curator_lens_challenge" if count > 2 else "exhibit_label_match"
        prompt = "වචනය ගැළපෙන සරල කේත ප්‍රදර්ශනයට තබන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return HeritageItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:{chapter}:parallel-v1",
        skill_id,
        chapter,
        role,
        prompt,
        (),
        "constructed-response",
        {},
        game,
    )

def generate_simpler_item(skill_id: str, *, seed: int, than: Mapping[str, object]) -> HeritageItem | None:
    """The same game and skill with fewer pairs to link than the failed game, from a fresh item."""

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    return simpler_matching_item(item, than=than)



def public_game_data(item: HeritageItem) -> dict[str, object]:
    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key != "target_mapping"},
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    common = {
        "command_token": str(game["command_token"]),
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "tap_alternative_used": True,
    }
    if game["response_kind"] == "past_bilingual_links":
        return {
            "kind": "past_bilingual_links",
            **common,
            "links": [
                {"sequence": index + 1, "english_token": source, "sinhala_token": target}
                for index, (source, target) in enumerate(mapping.items())
            ],
            "unlinked_english_tokens": [],
            "invalid_link_count": 0,
        }
    return {
        "kind": "heritage_exhibit_mapping",
        **common,
        "placements": [
            {"sequence": index + 1, "word_token": source, "exhibit_token": target}
            for index, (source, target) in enumerate(mapping.items())
        ],
        "unplaced_word_tokens": [],
        "invalid_drop_count": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | HeritageItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, HeritageItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_HERITAGE_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]:
        raise ValueError("MALFORMED_HERITAGE_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_HERITAGE_COMMAND")
    trace = response.get("interaction_trace")
    if (
        not isinstance(trace, list)
        or not trace
        or not all(isinstance(entry, str) for entry in trace)
    ):
        raise ValueError("INVALID_HERITAGE_TRACE")
    bilingual = response["kind"] == "past_bilingual_links"
    row_key, source_key, target_key = (
        ("links", "english_token", "sinhala_token")
        if bilingual
        else ("placements", "word_token", "exhibit_token")
    )
    empty_key, invalid_key = (
        ("unlinked_english_tokens", "invalid_link_count")
        if bilingual
        else ("unplaced_word_tokens", "invalid_drop_count")
    )
    mapping = game["target_mapping"]
    rows = response[row_key]
    assert isinstance(mapping, Mapping)
    if not isinstance(rows, list) or response[empty_key] != [] or len(rows) != len(mapping):
        raise ValueError("INCOMPLETE_HERITAGE_RESPONSE")
    submitted: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"sequence", source_key, target_key}
            or row["sequence"] != index
            or row[source_key] not in mapping
            or row[target_key] not in set(mapping.values()) | shown_tokens(game, target_key)
        ):
            raise ValueError("INVALID_HERITAGE_TOKEN_OR_SEQUENCE")
        submitted[str(row[source_key])] = str(row[target_key])
    if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
        raise ValueError("DUPLICATE_HERITAGE_SOURCE_OR_TARGET")
    for key in ("revisions", invalid_key):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100:
            raise ValueError("INVALID_HERITAGE_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_HERITAGE_COUNTER")
    correct = submitted == mapping
    error = (
        "english_sinhala_past_word_confusion" if bilingual else "heritage_word_exhibit_confusion"
    )
    return correct, "correct" if correct else error, dict(response)


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else remainder for name in MISCONCEPTIONS}
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
        return ["වචන හැඩය හෝ ප්‍රදර්ශනයේ ව්‍යුහය සසඳන්න; මෙය පිළිතුර නොපෙන්වයි."]
    if scaffold_type == "worked_parallel_example":
        return ["නව පුහුණු වචනයක් කියවමු.", "නව ඉලක්ක සසඳමු.", "නව සම්බන්ධය තබමු."]
    return ["එක් වචනයක් තෝරන්න.", "සියලු ඉලක්ක සසඳන්න.", "සම්බන්ධය තබා පරීක්ෂා කරන්න."]


def package_hash() -> str:
    payload = {
        "area": AREA_ID,
        "version": PACKAGE_VERSION,
        "source": [(row[1], row[2]) for row in SOURCE_PAIRS],
        "unresolved": UNRESOLVED_RENDERERS,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
