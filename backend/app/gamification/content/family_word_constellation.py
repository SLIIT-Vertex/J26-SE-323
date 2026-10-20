"""Development-only Theme 12 family vocabulary for G5-AREA-ENG-12.

Sinhala strings are unverified candidates. Grand - son and Grand - daughter
stay out of scored items until form review.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-12"
PACKAGE_VERSION = "g5-eng-family-constellation-draft-v1"
CATALOGUE_VERSION = "g5-eng-family-misconceptions-v1"
FEATURE_VERSION = "g5-eng-family-features-v1"
MAPPING_VERSION = "g5-eng-family-source-mapping-v1"
MODEL_VERSION = "g5-eng-family-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-family-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-family-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-family-parallel-v1"

Chapter = Literal["word_star", "constellation"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, source English, unverified Sinhala candidate
PAIRS = (
    ("father", "Father", "පියා"),
    ("mother", "Mother", "මව"),
    ("sister", "Sister", "සහෝදරිය"),
    ("brother", "Brother", "සහෝදරයා"),
    ("grandfather", "Grandfather", "මුත්තා"),
    ("grandmother", "Grandmother", "ආච්චි"),
    ("aunt", "Aunt", "නැන්දා"),
    ("uncle", "Uncle", "මාමා"),
)
BLOCKED_SOURCE_FORMS = ("Grand - son", "Grand - daughter", "grandson", "granddaughter")
STAGES: tuple[tuple[Chapter, tuple[str, ...]], ...] = (
    ("word_star", ("father", "mother")),
    ("word_star", ("father", "mother", "sister", "brother")),
    ("constellation", ("grandfather", "grandmother", "aunt", "uncle")),
)
MISCONCEPTIONS = (
    "english_sinhala_family_word_confusion",
    "father_mother_confusion",
    "sister_brother_confusion",
    "grandfather_grandmother_confusion",
    "aunt_uncle_confusion",
    "grandson_granddaughter_confusion",
    "grand_term_ending_confusion",
    "source_hyphen_spacing_confusion",
    "source_normalization_confusion",
    "sinhala_pairing_or_font_ambiguity",
    "incomplete_mapping_or_omission",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
BLOCKED_FORM_SKILL = "G5-ENG-FAMILY-FORM-02"


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-ENG-FAMILY-BILINGUAL-01", "word_star", "පාඩමේ ඉංග්‍රීසි සහ සිංහල වචන ගැළපීම", "easy-to-hard", "family_bilingual_links"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class FamilyConstellationItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> FamilyConstellationItem:
    if skill_id == BLOCKED_FORM_SKILL:
        raise ValueError("FAMILY_FORM_REVIEW_BLOCKED")
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("FAMILY_CONSTELLATION_ITEM_REQUEST_INVALID")
    chapter, keys = STAGES[seed % len(STAGES)]
    rows = [row for row in PAIRS if row[0] in keys]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submit", salt)
    english = [{"english_token": _token("e", key, salt), "text_en": text} for key, text, _ in rows]
    sinhala = [{"sinhala_token": _token("s", key, salt), "text_si": si} for key, _, si in reversed(rows)]
    rng.shuffle(english)
    rng.shuffle(sinhala)
    answer = {_token("e", key, salt): _token("s", key, salt) for key, _, _ in rows}
    game: dict[str, object] = {
        "response_kind": "family_bilingual_links",
        "activity_id": chapter,
        "command_token": command_token,
        "english_words": english,
        "sinhala_words": sinhala,
        "sinhala_pairing_status": "unverified_candidate",
        "target_mapping": answer,
    }
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    prompt = "මේ පාඩමේ ඉංග්‍රීසි වචනය සිංහල වචනයට සම්බන්ධ කරන්න."
    return FamilyConstellationItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]


def public_game_data(item: FamilyConstellationItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key != "target_mapping"}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    return {
        "kind": "family_bilingual_links",
        "command_token": str(game["command_token"]),
        "links": [{"sequence": index + 1, "english_token": source, "sinhala_token": target} for index, (source, target) in enumerate(mapping.items())],
        "unlinked_english_tokens": [],
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_link_count": 0,
        "tap_alternative_used": True,
    }


def validate_constructed_response(item: Mapping[str, object] | FamilyConstellationItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, FamilyConstellationItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_FAMILY_CONSTELLATION_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != "family_bilingual_links":
        raise ValueError("MALFORMED_FAMILY_CONSTELLATION_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_FAMILY_CONSTELLATION_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_FAMILY_CONSTELLATION_TRACE")
    rows = response["links"]
    if not isinstance(rows, list) or response["unlinked_english_tokens"] != []:
        raise ValueError("INCOMPLETE_FAMILY_LINKS")
    submitted = {str(row["english_token"]): str(row["sinhala_token"]) for row in rows if isinstance(row, Mapping)}
    answer = game["target_mapping"]
    assert isinstance(answer, Mapping)
    if len(submitted) != len(rows) or set(submitted) != set(answer) or len(set(submitted.values())) != len(submitted):
        raise ValueError("INCOMPLETE_OR_DUPLICATE_FAMILY_LINKS")
    correct = submitted == answer
    return correct, "correct" if correct else "english_sinhala_family_word_confusion", dict(response)


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
        return ["ඉංග්‍රීසි වචනය සහ සිංහල වචනය වෙන වෙනම කියවන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව ඉංග්‍රීසි වචනය කියවමු.", "ගැළපෙන සිංහල වචනය සොයමු.", "සම්බන්ධය තබා පරීක්ෂා කරමු."]
    return ["එක් ඉංග්‍රීසි වචනයක් තෝරන්න.", "සිංහල වචන සසඳන්න.", "සම්බන්ධය තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "pairs": [row[1] for row in PAIRS], "blocked": list(BLOCKED_SOURCE_FORMS)}, sort_keys=True).encode()).hexdigest()
