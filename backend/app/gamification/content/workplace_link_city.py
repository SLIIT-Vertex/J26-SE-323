"""Development-only Theme 11 occupation/workplace package for G5-AREA-ENG-11."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.gamification.content.simpler_items import shown_tokens, simpler_matching_item

AREA_ID = "G5-AREA-ENG-11"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-workplace-link-city-draft-v1"
CATALOGUE_VERSION = "g5-eng-work-misconceptions-v1"
FEATURE_VERSION = "g5-eng-work-features-v1"
MAPPING_VERSION = "g5-eng-work-source-mapping-v1"
MODEL_VERSION = "g5-eng-work-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-work-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-work-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-work-parallel-v1"

Chapter = Literal["job_badge_match", "work_route_connector", "city_network_challenge"]
Role = Literal["unsupported_before", "unsupported_after"]

PAIRS = (
    ("farmer", "Farmer", "paddy_field", "Paddy Field", 0, 0),
    ("fish_monger", "Fish monger", "fish_stall", "Fish Stall", 1, 1),
    ("teacher", "Teacher", "school", "School", 2, 2),
    ("doctor", "Doctor", "hospital", "Hospital", 3, 3),
    ("electrician", "Electrician", "buildings", "Buildings", 4, 4),
    ("mason", "Mason", "buildings", "Buildings", 5, 4),
    ("carpenter", "Carpenter", "workshop", "Workshop", 6, 5),
)
EXCLUDED_PENDING_INCLUSION_REVIEW = (("Fisherman", "Sea"),)
MISCONCEPTIONS = (
    "occupation_word_visual_confusion", "workplace_word_visual_confusion",
    "farmer_paddy_field_link_confusion", "fisherman_sea_link_confusion",
    "fish_monger_fish_stall_link_confusion", "teacher_school_doctor_hospital_confusion",
    "electrician_mason_shared_buildings_confusion", "carpenter_workshop_link_confusion",
    "one_to_one_assumption_on_shared_target", "source_spacing_or_regional_term_confusion",
    "emoji_or_code_scene_ambiguity", "incomplete_mapping_or_omission", "unknown_or_other",
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
    AtomicSkill("G5-ENG-WORK-VOCAB-01", "job_badge_match", "රැකියා සහ සේවා ස්ථාන වචන හඳුනාගැනීම", "easy-to-hard", "work_vocabulary_mapping"),
    AtomicSkill("G5-ENG-WORK-PLACE-02", "work_route_connector", "පාඩමේ රැකියා සහ ස්ථාන සම්බන්ධතා ගොඩනැගීම", "easy-to-hard", "occupation_place_links"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class WorkplaceLinkItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> WorkplaceLinkItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("WORKPLACE_LINK_ITEM_REQUEST_INVALID")
    rng = random.Random(int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big"))
    salt = f"{skill_id}:{role}:{seed}"
    if skill_id == "G5-ENG-WORK-VOCAB-01":
        rows = list(PAIRS)
        rng.shuffle(rows)
        rows = rows[: (3 if seed % 2 == 0 else 4)]
        words = [{"word_token": _token("w", role_key, salt), "text_en": role_text} for role_key, role_text, *_ in rows]
        representations = [{"representation_token": _token("r", role_key, salt), "renderer_variant": role_variant} for role_key, _, _, _, role_variant, _ in reversed(rows)]
        game = {"response_kind": "work_vocabulary_mapping", "activity_id": "job_badge_match", "command_token": _token("cmd", "submit", salt), "words": words, "representations": representations, "target_mapping": {_token("w", key, salt): _token("r", key, salt) for key, *_ in rows}}
        chapter: Chapter = "job_badge_match"
        prompt = "ඉංග්‍රීසි ලාංඡනය ගැළපෙන කාඩ්පතට සම්බන්ධ කරන්න."
    else:
        hard = seed % 2 == 1
        rows = list(PAIRS if hard else PAIRS[:4])
        occupations = [{"occupation_token": _token("o", key, salt), "text_en": text} for key, text, *_ in rows]
        unique_places: dict[str, tuple[str, int]] = {}
        for _, _, place_key, place_text, _, place_variant in rows:
            unique_places[place_key] = (place_text, place_variant)
        places = [{"place_token": _token("p", key, salt), "text_en": text, "renderer_variant": variant, "capacity": sum(1 for row in rows if row[2] == key)} for key, (text, variant) in unique_places.items()]
        rng.shuffle(occupations); rng.shuffle(places)
        game = {"response_kind": "occupation_place_links", "activity_id": "city_network_challenge" if hard else "work_route_connector", "command_token": _token("cmd", "link", salt), "occupations": occupations, "places": places, "target_links": {_token("o", role_key, salt): _token("p", place_key, salt) for role_key, _, place_key, *_ in rows}}
        chapter = "city_network_challenge" if hard else "work_route_connector"
        prompt = "මෙම පාඩමේ යුගල සම්බන්ධ කරන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return WorkplaceLinkItem(f"{skill_id}:{role}", revision, f"{skill_id}:{chapter}:parallel-v1", skill_id, chapter, role, prompt, (), "constructed-response", {}, game)  # type: ignore[arg-type]

def generate_simpler_item(skill_id: str, *, seed: int, than: Mapping[str, object]) -> WorkplaceLinkItem | None:
    """The same game and skill with fewer pairs to link than the failed game, from a fresh item."""

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    return simpler_matching_item(item, than=than)



def public_game_data(item: WorkplaceLinkItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{key: value for key, value in item.game_data.items() if key not in {"target_mapping", "target_links"}}}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {"command_token": str(game["command_token"]), "interaction_trace": ["server:correct"], "revisions": 0, "tap_alternative_used": True}
    if game["response_kind"] == "work_vocabulary_mapping":
        mapping = game["target_mapping"]; assert isinstance(mapping, Mapping)
        return {"kind": "work_vocabulary_mapping", **common, "placements": [{"sequence": i + 1, "word_token": source, "representation_token": target} for i, (source, target) in enumerate(mapping.items())], "unplaced_word_tokens": [], "invalid_drop_count": 0}
    links = game["target_links"]; assert isinstance(links, Mapping)
    return {"kind": "occupation_place_links", **common, "links": [{"sequence": i + 1, "occupation_token": source, "place_token": target} for i, (source, target) in enumerate(links.items())], "unlinked_occupation_tokens": [], "invalid_link_count": 0}


def validate_constructed_response(item: Mapping[str, object] | WorkplaceLinkItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, WorkplaceLinkItem) else item["game_data"]
    if not isinstance(game, Mapping): raise TypeError("MALFORMED_WORKPLACE_LINK_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]: raise ValueError("MALFORMED_WORKPLACE_LINK_RESPONSE")
    if response.get("command_token") != game["command_token"]: raise ValueError("STALE_WORKPLACE_LINK_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(value, str) for value in trace): raise ValueError("INVALID_WORKPLACE_LINK_TRACE")
    vocabulary = response["kind"] == "work_vocabulary_mapping"
    answer_key = "target_mapping" if vocabulary else "target_links"; rows_key = "placements" if vocabulary else "links"
    source_key = "word_token" if vocabulary else "occupation_token"; target_key = "representation_token" if vocabulary else "place_token"
    empty_key = "unplaced_word_tokens" if vocabulary else "unlinked_occupation_tokens"; invalid_key = "invalid_drop_count" if vocabulary else "invalid_link_count"
    answer = game[answer_key]; rows = response[rows_key]; assert isinstance(answer, Mapping)
    if not isinstance(rows, list) or response[empty_key] != [] or len(rows) != len(answer): raise ValueError("INCOMPLETE_WORKPLACE_LINK_RESPONSE")
    allowed_targets = set(answer.values()) | shown_tokens(game, target_key)
    submitted: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping) or set(row) != {"sequence", source_key, target_key} or row["sequence"] != index or row[source_key] not in answer or row[target_key] not in allowed_targets: raise ValueError("INVALID_WORKPLACE_LINK_TOKEN_OR_SEQUENCE")
        submitted[str(row[source_key])] = str(row[target_key])
    if len(submitted) != len(rows) or (vocabulary and len(set(submitted.values())) != len(rows)): raise ValueError("DUPLICATE_WORKPLACE_LINK_SOURCE_OR_TARGET")
    for key in ("revisions", invalid_key):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100: raise ValueError("INVALID_WORKPLACE_INTERACTION_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool): raise TypeError("INVALID_WORKPLACE_INTERACTION_COUNTER")
    correct = submitted == answer
    return correct, "correct" if correct else ("occupation_word_visual_confusion" if vocabulary else "one_to_one_assumption_on_shared_target"), dict(response)


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"; confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72)); remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1); probabilities = {key: confidence if key == primary else remainder for key in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    relational = game["response_kind"] == "occupation_place_links"
    if scaffold_type == "visual_guidance": return ["එක් නමක් තෝරා කාඩ්පත් හෝ ස්ථාන ලේබල් සසඳන්න."]
    if scaffold_type == "worked_parallel_example": return ["නව නමක් කියවමු.", "නව කාඩ්පතක් සොයමු.", "නව යුගලය සම්බන්ධ කරමු."]
    return ["රැකියාවක් තෝරන්න.", "පාඩමේ ස්ථාන බලන්න.", "එකම ස්ථානයට සම්බන්ධතා දෙකක් තිබිය හැකි බව මතක තබා සම්බන්ධ කරන්න."] if relational else ["ලාංඡනය කියවන්න.", "කේත රූප සසඳන්න.", "ගැළපෙන කාඩ්පතට තබන්න."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"area": AREA_ID, "version": PACKAGE_VERSION, "pairs": [(row[1], row[3]) for row in PAIRS], "excluded": EXCLUDED_PENDING_INCLUSION_REVIEW}, sort_keys=True).encode()).hexdigest()
