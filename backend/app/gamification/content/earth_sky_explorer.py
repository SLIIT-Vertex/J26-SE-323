"""Development-only Theme 13 Earth & Sky package for G5-AREA-ENG-13."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-13"
PACKAGE_VERSION = "g5-eng-earth-sky-explorer-draft-v1"
CATALOGUE_VERSION = "g5-eng-earth-sky-misconceptions-v1"
FEATURE_VERSION = "g5-eng-earth-sky-features-v1"
MAPPING_VERSION = "g5-eng-earth-sky-source-mapping-v1"
MODEL_VERSION = "g5-eng-earth-sky-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-earth-sky-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-earth-sky-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-earth-sky-parallel-v1"

Chapter = Literal["skyword_signal_bridge", "panorama_label_quest", "nature_lens_detective"]
Role = Literal["unsupported_before", "unsupported_after"]

# key, exact source English, exact visible Sinhala, renderer variant or None.
SOURCE_PAIRS = (
    ("sky", "Sky", "අහස", 0), ("sun", "Sun", "ඉර", 1),
    ("moon", "Moon", "සඳ", 2), ("stars", "Stars", "තරු", 3),
    ("rainbow", "Rainbow", "දේදුන්න", 4), ("wind", "Wind", "සුළග", None),
    ("clouds", "Clouds", "වලාකුළු", 5), ("rain", "Rain", "වැස්ස", 6),
    ("river", "River", "ගඟ", 7), ("hill", "Hill", "කන්ද", None),
    ("mountain", "Mountain", "කන්ද", None), ("rain_drops", "Rain drops", "වැහි බිංදු", 8),
    ("lightening", "Lightening", "විදුලි කෙටීම", None), ("floods", "Floods", "ගංවතුර", 9),
    ("thunder", "Thunder", "ගිගුරුම්", None), ("sea", "Sea", "මුහුද", 10),
    ("beach", "Beach", "වෙරළ", 11), ("mist", "Mist", "මීදුම", None),
    ("waterfall", "Waterfall", "දිය ඇල්ල", 12), ("well", "Well", "ළිඳ", 13),
    ("pond", "Pond", "පොකුණ", 14), ("tank", "Tank", "වැව", None),
)
BLOCKED_FOR_ALL_SCORING = ("Lightening",)
BLOCKED_BILINGUAL_CONTRASTS = ("Hill", "Mountain", "Tank")
BLOCKED_VISUAL_FORMS = ("Lightening", "Thunder", "Tank", "Hill", "Mountain", "Wind", "Mist")

MISCONCEPTIONS = (
    "english_sinhala_earth_sky_word_confusion", "earth_sky_word_scene_confusion",
    "sun_moon_stars_confusion", "clouds_mist_confusion", "rain_raindrops_confusion",
    "hill_mountain_confusion", "river_sea_confusion", "pond_tank_well_confusion",
    "sea_beach_confusion", "waterfall_river_confusion", "lightening_lightning_source_confusion",
    "source_spacing_or_plural_form_confusion", "emoji_or_code_scene_ambiguity",
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
    AtomicSkill("G5-ENG-EARTHSKY-BILINGUAL-01", "skyword_signal_bridge", "ඉංග්‍රීසි සහ සිංහල වචන සම්බන්ධ කිරීම", "easy-to-hard", "earth_sky_bilingual_links"),
    AtomicSkill("G5-ENG-EARTHSKY-VISUAL-02", "panorama_label_quest", "ඉංග්‍රීසි වචන සහ කේත දර්ශන සම්බන්ධ කිරීම", "easy-to-hard", "earth_sky_scene_mapping"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class EarthSkyItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> EarthSkyItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("EARTH_SKY_ITEM_REQUEST_INVALID")
    rng = random.Random(int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big"))
    salt = f"{skill_id}:{role}:{seed}"
    if skill_id == "G5-ENG-EARTHSKY-BILINGUAL-01":
        eligible = [row for row in SOURCE_PAIRS if row[1] not in BLOCKED_FOR_ALL_SCORING + BLOCKED_BILINGUAL_CONTRASTS]
        rng.shuffle(eligible)
        rows = eligible[: (3 if seed % 2 == 0 else 4)]
        english = [{"english_token": _token("e", row[0], salt), "text_en": row[1]} for row in rows]
        sinhala = [{"sinhala_token": _token("s", row[0], salt), "text_si": row[2]} for row in reversed(rows)]
        game = {"response_kind": "earth_sky_bilingual_links", "activity_id": "skyword_signal_bridge", "command_token": _token("cmd", "bridge", salt), "english_words": english, "sinhala_words": sinhala, "target_mapping": {_token("e", row[0], salt): _token("s", row[0], salt) for row in rows}}
        chapter: Chapter = "skyword_signal_bridge"
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන සිංහල වචනයට සම්බන්ධ කරන්න."
    else:
        eligible = [row for row in SOURCE_PAIRS if row[3] is not None and row[1] not in BLOCKED_VISUAL_FORMS]
        rng.shuffle(eligible)
        rows = eligible[: (3 if seed % 2 == 0 else 4)]
        words = [{"word_token": _token("w", row[0], salt), "text_en": row[1]} for row in rows]
        scenes = [{"scene_token": _token("c", row[0], salt), "renderer_variant": row[3]} for row in reversed(rows)]
        hard = len(rows) == 4
        game = {"response_kind": "earth_sky_scene_mapping", "activity_id": "nature_lens_detective" if hard else "panorama_label_quest", "command_token": _token("cmd", "panorama", salt), "words": words, "scenes": scenes, "target_mapping": {_token("w", row[0], salt): _token("c", row[0], salt) for row in rows}, "lens_enabled": hard}
        chapter = "nature_lens_detective" if hard else "panorama_label_quest"
        prompt = "ඉංග්‍රීසි වචනය ගැළපෙන දර්ශන කාඩ්පතට තබන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return EarthSkyItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]


def public_game_data(item: EarthSkyItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key != "target_mapping"}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    mapping = game["target_mapping"]
    assert isinstance(mapping, Mapping)
    common = {"command_token": str(game["command_token"]), "interaction_trace": ["server:correct"], "revisions": 0, "tap_alternative_used": True}
    if game["response_kind"] == "earth_sky_bilingual_links":
        return {"kind": "earth_sky_bilingual_links", **common, "links": [{"sequence": index + 1, "english_token": source, "sinhala_token": target} for index, (source, target) in enumerate(mapping.items())], "unlinked_english_tokens": [], "invalid_link_count": 0}
    return {"kind": "earth_sky_scene_mapping", **common, "placements": [{"sequence": index + 1, "word_token": source, "scene_token": target} for index, (source, target) in enumerate(mapping.items())], "unplaced_word_tokens": [], "invalid_drop_count": 0}


def validate_constructed_response(item: Mapping[str, object] | EarthSkyItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, EarthSkyItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_EARTH_SKY_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]:
        raise ValueError("MALFORMED_EARTH_SKY_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_EARTH_SKY_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace):
        raise ValueError("INVALID_EARTH_SKY_TRACE")
    bilingual = response["kind"] == "earth_sky_bilingual_links"
    rows_key, source_key, target_key = ("links", "english_token", "sinhala_token") if bilingual else ("placements", "word_token", "scene_token")
    empty_key, invalid_key = ("unlinked_english_tokens", "invalid_link_count") if bilingual else ("unplaced_word_tokens", "invalid_drop_count")
    answer = game["target_mapping"]
    rows = response[rows_key]
    assert isinstance(answer, Mapping)
    if not isinstance(rows, list) or response[empty_key] != [] or len(rows) != len(answer):
        raise ValueError("INCOMPLETE_EARTH_SKY_RESPONSE")
    submitted: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping) or set(row) != {"sequence", source_key, target_key} or row["sequence"] != index or row[source_key] not in answer or row[target_key] not in set(answer.values()):
            raise ValueError("INVALID_EARTH_SKY_TOKEN_OR_SEQUENCE")
        submitted[str(row[source_key])] = str(row[target_key])
    if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
        raise ValueError("DUPLICATE_EARTH_SKY_SOURCE_OR_TARGET")
    for key in ("revisions", invalid_key):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100:
            raise ValueError("INVALID_EARTH_SKY_INTERACTION_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_EARTH_SKY_INTERACTION_COUNTER")
    correct = submitted == answer
    error = "english_sinhala_earth_sky_word_confusion" if bilingual else "earth_sky_word_scene_confusion"
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
    visual = game["response_kind"] == "earth_sky_scene_mapping"
    if scaffold_type == "visual_guidance":
        return ["වචනය කියවා දර්ශනයේ හැඩය, සීමාව සහ රටාව සසඳන්න." if visual else "ඉංග්‍රීසි සහ සිංහල වචන වෙන වෙනම කියවන්න."]
    if scaffold_type == "worked_parallel_example":
        return ["නව වචනයක් කියවමු.", "නව ඉලක්ක සසඳමු.", "නව සම්බන්ධය තබමු."]
    return ["එක් වචනයක් තෝරන්න.", "සියලු ඉලක්ක සසඳන්න.", "සම්බන්ධය තබා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "source": [(row[1], row[2]) for row in SOURCE_PAIRS], "blocked": [BLOCKED_FOR_ALL_SCORING, BLOCKED_BILINGUAL_CONTRASTS, BLOCKED_VISUAL_FORMS]}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
