"""Development-only Theme 2 vocabulary content for G5-AREA-ENG-02."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-02"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-sri-lanka-discovery-draft-v1"
CATALOGUE_VERSION = "g5-eng-sri-lanka-misconceptions-v1"
FEATURE_VERSION = "g5-eng-sri-lanka-features-v1"
MAPPING_VERSION = "g5-eng-sri-lanka-source-mapping-v1"
MODEL_VERSION = "g5-eng-sri-lanka-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-sri-lanka-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-sri-lanka-mapping-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-sri-lanka-parallel-v1"

Chapter = Literal["word_explorer", "national_gallery", "community_sort"]
Role = Literal["unsupported_before", "unsupported_after"]

VOCABULARY = (
    ("temple", "Temple", "පන්සල", "place"),
    ("church", "Church", "පල්ලිය", "place"),
    ("mosque", "Mosque", "මස්ජිදය", "place"),
    ("kovil", "Kovil", "කෝවිල", "place"),
    ("crib", "Crib", "ගවලෙන", "cultural_object"),
    ("christmas_tree", "Christmas Tree", "නත්තල් ගස", "cultural_object"),
    ("kolam", "Kolam", "කෝලම් රටා", "cultural_object"),
    ("vesak_lantern", "Vesak Lantern", "වෙසක් කූඩුව", "cultural_object"),
)
NATIONAL_PAIRS = (
    ("national_bird", "National Bird", "jungle_fowl", "Jungle Fowl"),
    ("national_flower", "National Flower", "blue_waterlily", "Blue Waterlily"),
    ("national_tree", "National Tree", "na_tree", "'Na' Tree"),
    ("national_game", "National Game", "volleyball", "Volleyball"),
)
MISCONCEPTIONS = (
    "national_category_vs_exemplar_confusion",
    "bird_vs_flower_exemplar_confusion",
    "tree_vs_flower_exemplar_confusion",
    "national_game_term_confusion",
    "place_vs_cultural_object_confusion",
    "temple_church_mosque_kovil_lexical_confusion",
    "crib_vs_christmas_tree_lexical_confusion",
    "kolam_vs_vesak_lantern_lexical_confusion",
    "english_sinhala_label_mapping_confusion",
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
        "G5-ENG-SL-VOCAB-RECOGNITION-01",
        "word_explorer",
        "ඉංග්‍රීසි වචන සහ සිංහල අර්ථ සම්බන්ධ කිරීම",
        "easy",
        "semantic_label_mapping",
    ),
    AtomicSkill(
        "G5-ENG-SL-NATIONAL-PAIR-01",
        "national_gallery",
        "ජාතික ප්‍රවර්ග සහ නිදසුන් සම්බන්ධ කිරීම",
        "medium",
        "category_exemplar_mapping",
    ),
    AtomicSkill(
        "G5-ENG-SL-CULTURAL-GROUP-01",
        "community_sort",
        "ස්ථාන සහ සංස්කෘතික වස්තු වර්ග කිරීම",
        "medium-hard",
        "semantic_grouping",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class SriLankaDiscoveryItem:
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
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def generate_item(skill_id: str, *, role: str, seed: int) -> SriLankaDiscoveryItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("SRI_LANKA_DISCOVERY_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    salt = f"{skill_id}:{role}:{seed}"
    command_token = _token("cmd", "submission", salt)
    if skill.chapter == "word_explorer":
        rows = list(VOCABULARY)
        rng.shuffle(rows)
        rows = rows[:4]
        labels = [
            {"label_id": _token("lbl", key, salt), "text_en": english}
            for key, english, _sinhala, _group in rows
        ]
        destinations = [
            {"destination_id": _token("dst", key, salt), "text_si": sinhala}
            for key, _english, sinhala, _group in reversed(rows)
        ]
        target = {
            _token("lbl", key, salt): _token("dst", key, salt)
            for key, _english, _sinhala, _group in rows
        }
        game: dict[str, object] = {
            "response_kind": "semantic_label_mapping",
            "activity_id": "word_explorer",
            "command_token": command_token,
            "labels": labels,
            "destinations": destinations,
            "target_mapping": target,
        }
        prompt = "ඉංග්‍රීසි වචනය එහි සිංහල අර්ථයට සම්බන්ධ කරන්න."
    elif skill.chapter == "national_gallery":
        rows = list(NATIONAL_PAIRS)
        rng.shuffle(rows)
        categories = [
            {"category_id": _token("cat", category, salt), "text_en": category_text}
            for category, category_text, _exemplar, _exemplar_text in rows
        ]
        exemplars = [
            {"exemplar_id": _token("ex", exemplar, salt), "text_en": exemplar_text}
            for _category, _category_text, exemplar, exemplar_text in reversed(rows)
        ]
        target = {
            _token("cat", category, salt): _token("ex", exemplar, salt)
            for category, _category_text, exemplar, _exemplar_text in rows
        }
        game = {
            "response_kind": "category_exemplar_mapping",
            "activity_id": "national_gallery",
            "command_token": command_token,
            "categories": categories,
            "exemplars": exemplars,
            "target_mapping": target,
        }
        prompt = "ජාතික ප්‍රවර්ගය නිවැරදි ඉංග්‍රීසි නිදසුනට සම්බන්ධ කරන්න."
    else:
        rows = list(VOCABULARY)
        rng.shuffle(rows)
        groups = [
            {"group_id": _token("grp", "place", salt), "text_en": "Places"},
            {
                "group_id": _token("grp", "cultural_object", salt),
                "text_en": "Cultural & festival objects",
            },
        ]
        members = [
            {"member_id": _token("mem", key, salt), "text_en": english}
            for key, english, _sinhala, _group in rows
        ]
        target = {
            _token("grp", group, salt): sorted(
                _token("mem", key, salt)
                for key, _english, _sinhala, row_group in rows
                if row_group == group
            )
            for group in ("place", "cultural_object")
        }
        game = {
            "response_kind": "semantic_grouping",
            "activity_id": "community_sort",
            "command_token": command_token,
            "groups": groups,
            "members": members,
            "target_groups": target,
        }
        prompt = "ඉංග්‍රීසි වචන නිවැරදි කණ්ඩායමට වර්ග කරන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return SriLankaDiscoveryItem(
        item_id=f"{skill_id}:{role}",
        revision_id=revision,
        parallel_family_id=f"{skill_id}:parallel-v1",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,  # type: ignore[arg-type]
        prompt_si=prompt,
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def public_game_data(item: SriLankaDiscoveryItem) -> dict[str, object]:
    hidden = {"target_mapping", "target_groups"}
    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key not in hidden},
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    common = {
        "kind": kind,
        "command_token": str(game["command_token"]),
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }
    if kind == "semantic_label_mapping":
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        return {
            **common,
            "placements": [
                {"sequence": i + 1, "label_id": label, "destination_id": destination}
                for i, (label, destination) in enumerate(mapping.items())
            ],
            "unplaced_label_ids": [],
        }
    if kind == "category_exemplar_mapping":
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        return {
            **common,
            "mappings": [
                {"sequence": i + 1, "category_id": category, "exemplar_id": exemplar}
                for i, (category, exemplar) in enumerate(mapping.items())
            ],
        }
    groups = game["target_groups"]
    assert isinstance(groups, Mapping)
    return {
        **common,
        "groups": [
            {"group_id": group, "ordered_member_ids": list(members)}
            for group, members in groups.items()
        ],
        "unassigned_member_ids": [],
    }


def _ids(rows: object, id_key: str) -> set[str]:
    if not isinstance(rows, list):
        raise TypeError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"sequence", id_key, "destination_id"}:
            raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
        result.add(str(row[id_key]))
    return result


def validate_constructed_response(
    item: Mapping[str, object] | SriLankaDiscoveryItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, SriLankaDiscoveryItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_SRI_LANKA_DISCOVERY_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != game["response_kind"]:
        raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_SRI_LANKA_DISCOVERY_COMMAND")
    trace = response.get("interaction_trace")
    if (
        not isinstance(trace, list)
        or not trace
        or not all(isinstance(value, str) for value in trace)
    ):
        raise ValueError("INVALID_SRI_LANKA_DISCOVERY_TRACE")
    kind = str(game["response_kind"])
    if kind == "semantic_label_mapping":
        placements = response["placements"]
        labels = _ids(placements, "label_id")
        allowed = {str(row["label_id"]) for row in game["labels"]}  # type: ignore[index,union-attr]
        if labels != allowed or response["unplaced_label_ids"] != []:
            raise ValueError("INCOMPLETE_OR_DUPLICATE_LABEL_MAPPING")
        submitted = {str(row["label_id"]): str(row["destination_id"]) for row in placements}  # type: ignore[union-attr]
        correct = submitted == game["target_mapping"]
        error = "english_sinhala_label_mapping_confusion"
    elif kind == "category_exemplar_mapping":
        mappings = response["mappings"]
        if not isinstance(mappings, list):
            raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
        submitted = {}
        for row in mappings:
            if not isinstance(row, Mapping) or set(row) != {
                "sequence",
                "category_id",
                "exemplar_id",
            }:
                raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
            submitted[str(row["category_id"])] = str(row["exemplar_id"])
        if len(submitted) != len(mappings) or set(submitted) != set(game["target_mapping"]):  # type: ignore[arg-type]
            raise ValueError("INCOMPLETE_OR_DUPLICATE_CATEGORY_MAPPING")
        correct = submitted == game["target_mapping"]
        error = "national_category_vs_exemplar_confusion"
    else:
        groups = response["groups"]
        if not isinstance(groups, list):
            raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
        submitted_groups: dict[str, list[str]] = {}
        all_members: list[str] = []
        for row in groups:
            if not isinstance(row, Mapping) or set(row) != {"group_id", "ordered_member_ids"}:
                raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
            members = row["ordered_member_ids"]
            if not isinstance(members, list) or not all(
                isinstance(value, str) for value in members
            ):
                raise ValueError("MALFORMED_SRI_LANKA_DISCOVERY_RESPONSE")
            submitted_groups[str(row["group_id"])] = sorted(members)
            all_members.extend(members)
        allowed_members = {str(row["member_id"]) for row in game["members"]}  # type: ignore[index,union-attr]
        if set(all_members) != allowed_members or len(all_members) != len(set(all_members)):
            raise ValueError("INCOMPLETE_OR_DUPLICATE_SEMANTIC_GROUPING")
        correct = (
            submitted_groups == game["target_groups"] and response["unassigned_member_ids"] == []
        )
        error = "place_vs_cultural_object_confusion"
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
    if scaffold_type == "visual_guidance":
        return ["වචනයේ අර්ථ කණ්ඩායම හඳුනාගෙන ගැළපෙන ස්ථානය බලන්න."]
    if scaffold_type == "worked_parallel_example":
        return [
            "නව උදාහරණයක ඉංග්‍රීසි වචනය කියවමු.",
            "එහි අර්ථය හෝ ප්‍රවර්ගය හඳුනාගනිමු.",
            "ගැළපෙන ස්ථානයට තබා සම්බන්ධය පරීක්ෂා කරමු.",
        ]
    return [
        "එක් වචනයක් තෝරන්න.",
        "එය ස්ථානයක්ද, වස්තුවක්ද, ජාතික ප්‍රවර්ගයක්ද බලන්න.",
        "ගැළපෙන තැනට තබා ඉතිරි වචන නැවත පරීක්ෂා කරන්න.",
    ]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "area": AREA_ID,
                "version": PACKAGE_VERSION,
                "skills": [skill.skill_id for skill in ATOMIC_SKILLS],
                "vocabulary": [row[0] for row in VOCABULARY],
                "national_pairs": [row[0] for row in NATIONAL_PAIRS],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
