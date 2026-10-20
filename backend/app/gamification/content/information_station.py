"""Development-only Theme 15 Information Station content."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-15"
PACKAGE_VERSION = "g5-eng-information-station-draft-v1"
CATALOGUE_VERSION = "g5-eng-info-misconceptions-v1"
FEATURE_VERSION = "g5-eng-info-features-v1"
MAPPING_VERSION = "g5-eng-info-source-mapping-v1"
MODEL_VERSION = "g5-eng-info-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-info-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-info-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-info-parallel-v1"
Chapter = Literal["word_signal_bridge", "information_object_dock", "signal_console_challenge"]
Role = Literal["unsupported_before", "unsupported_after"]
SOURCE_PAIRS = (
    ("letter", "Letter", "ලියුම", None),
    ("newspapers", "Newspapers", "පුවත්පත්", 0),
    ("telephone", "Telephone", "දුරකථනය", 1),
    ("post", "Post", "තැපෑල", None),
)
BLOCKED_VISUAL_FORMS = ("Letter", "Post")
MISCONCEPTIONS = (
    "english_sinhala_information_word_confusion",
    "information_word_object_confusion",
    "letter_alphabet_message_sense_confusion",
    "post_mail_place_action_sense_confusion",
    "letter_post_confusion",
    "newspaper_post_confusion",
    "telephone_device_call_confusion",
    "source_plural_form_confusion",
    "sinhala_pairing_or_font_ambiguity",
    "emoji_or_code_object_ambiguity",
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
        "G5-ENG-INFO-BILINGUAL-01",
        "word_signal_bridge",
        "ඉංග්‍රීසි සහ සිංහල තොරතුරු වචන සම්බන්ධ කිරීම",
        "easy-to-hard",
        "information_bilingual_links",
    ),
    AtomicSkill(
        "G5-ENG-INFO-VISUAL-02",
        "information_object_dock",
        "අනුමත තොරතුරු වචන සහ කේත වස්තු සම්බන්ධ කිරීම",
        "easy-to-hard",
        "information_object_mapping",
    ),
)
SKILLS = {x.skill_id: x for x in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class InformationItem:
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


def _token(p: str, v: str, s: str) -> str:
    return f"{p}-{hashlib.sha256(f'{s}:{v}'.encode()).hexdigest()[:12]}"


def generate_item(skill_id: str, *, role: str, seed: int) -> InformationItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INFORMATION_ITEM_REQUEST_INVALID")
    rng = random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    )
    salt = f"{skill_id}:{role}:{seed}"
    if skill_id == "G5-ENG-INFO-BILINGUAL-01":
        rows = list(SOURCE_PAIRS)
        rng.shuffle(rows)
        rows = rows[: (2 if seed % 2 == 0 else 4)]
        english = [{"english_token": _token("e", x[0], salt), "text_en": x[1]} for x in rows]
        sinhala = [
            {"sinhala_token": _token("s", x[0], salt), "text_si": x[2]} for x in reversed(rows)
        ]
        game = {
            "response_kind": "information_bilingual_links",
            "activity_id": "signal_console_challenge" if len(rows) > 2 else "word_signal_bridge",
            "command_token": _token("cmd", "bridge", salt),
            "english_words": english,
            "sinhala_words": sinhala,
            "target_mapping": {_token("e", x[0], salt): _token("s", x[0], salt) for x in rows},
        }
        chapter: Chapter = "signal_console_challenge" if len(rows) > 2 else "word_signal_bridge"
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන සිංහල වචනයට සම්බන්ධ කරන්න."
    else:
        rows = [x for x in SOURCE_PAIRS if x[3] is not None and x[1] not in BLOCKED_VISUAL_FORMS]
        rng.shuffle(rows)
        words = [{"word_token": _token("w", x[0], salt), "text_en": x[1]} for x in rows]
        objects = [
            {"object_token": _token("o", x[0], salt), "renderer_variant": x[3]}
            for x in reversed(rows)
        ]
        game = {
            "response_kind": "information_object_mapping",
            "activity_id": "information_object_dock",
            "command_token": _token("cmd", "dock", salt),
            "words": words,
            "objects": objects,
            "target_mapping": {_token("w", x[0], salt): _token("o", x[0], salt) for x in rows},
        }
        chapter = "information_object_dock"
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන කේත වස්තුවට තබන්න."
    rev = f"{skill_id}:{role}:{seed % 100000}@v1"
    return InformationItem(
        f"{skill_id}:{role}",
        rev,
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


def public_game_data(item: InformationItem) -> dict[str, object]:
    return {
        "chapter": item.chapter,
        **{k: v for k, v in item.game_data.items() if k != "target_mapping"},
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
    if game["response_kind"] == "information_bilingual_links":
        return {
            "kind": "information_bilingual_links",
            **common,
            "links": [
                {"sequence": i + 1, "english_token": s, "sinhala_token": t}
                for i, (s, t) in enumerate(mapping.items())
            ],
            "unlinked_english_tokens": [],
            "invalid_link_count": 0,
        }
    return {
        "kind": "information_object_mapping",
        **common,
        "placements": [
            {"sequence": i + 1, "word_token": s, "object_token": t}
            for i, (s, t) in enumerate(mapping.items())
        ],
        "unplaced_word_tokens": [],
        "invalid_drop_count": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | InformationItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, InformationItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_INFORMATION_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]:
        raise ValueError("MALFORMED_INFORMATION_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_INFORMATION_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(x, str) for x in trace):
        raise ValueError("INVALID_INFORMATION_TRACE")
    bilingual = response["kind"] == "information_bilingual_links"
    rk, sk, tk = (
        ("links", "english_token", "sinhala_token")
        if bilingual
        else ("placements", "word_token", "object_token")
    )
    ek, ik = (
        ("unlinked_english_tokens", "invalid_link_count")
        if bilingual
        else ("unplaced_word_tokens", "invalid_drop_count")
    )
    mapping = game["target_mapping"]
    rows = response[rk]
    assert isinstance(mapping, Mapping)
    if not isinstance(rows, list) or response[ek] != [] or len(rows) != len(mapping):
        raise ValueError("INCOMPLETE_INFORMATION_RESPONSE")
    submitted = {}
    for i, row in enumerate(rows, 1):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"sequence", sk, tk}
            or row["sequence"] != i
            or row[sk] not in mapping
            or row[tk] not in set(mapping.values())
        ):
            raise ValueError("INVALID_INFORMATION_TOKEN_OR_SEQUENCE")
        submitted[str(row[sk])] = str(row[tk])
    if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
        raise ValueError("DUPLICATE_INFORMATION_SOURCE_OR_TARGET")
    for key in ("revisions", ik):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100:
            raise ValueError("INVALID_INFORMATION_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_INFORMATION_COUNTER")
    correct = submitted == mapping
    error = (
        "english_sinhala_information_word_confusion"
        if bilingual
        else "information_word_object_confusion"
    )
    return correct, "correct" if correct else error, dict(response)


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {x: confidence if x == primary else remainder for x in MISCONCEPTIONS}
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
    if scaffold_type == "visual_guidance":
        return ["වචන හෝ කේත වස්තු වෙන වෙනම සසඳන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව වචනයක් කියවමු.", "නව ඉලක්ක සසඳමු.", "නව සම්බන්ධය තබමු."]
    return ["එක් වචනයක් තෝරන්න.", "සියලු ඉලක්ක සසඳන්න.", "සම්බන්ධය තබා පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "area": AREA_ID,
                "version": PACKAGE_VERSION,
                "source": [(x[1], x[2]) for x in SOURCE_PAIRS],
                "blocked": BLOCKED_VISUAL_FORMS,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
