"""Development-only Grade 5 English action-command content for G5-AREA-ENG-01."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

AREA_ID = "G5-AREA-ENG-01"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-classroom-action-quest-draft-v1"
CATALOGUE_VERSION = "g5-eng-action-command-misconceptions-v1"
FEATURE_VERSION = "g5-eng-action-command-features-v1"
MAPPING_VERSION = "g5-eng-action-command-source-mapping-v1"
MODEL_VERSION = "g5-eng-action-command-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-action-command-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-action-command-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-action-command-parallel-v1"

Chapter = Literal["action_mirror", "classroom_dash", "come_back"]
Role = Literal["unsupported_before", "unsupported_after"]

BODY_COMMANDS = (
    ("bend", "Bend", "නැමෙන්න", "bent", "down", "front", "standing"),
    (
        "stretch_arms",
        "Stretch your arms",
        "ඔබේ අත් දිගහරින්න",
        "upright",
        "stretched",
        "front",
        "standing",
    ),
    ("arms_down", "Put your arms down", "ඔබේ අත් පහළට දමන්න", "upright", "down", "front", "standing"),
    ("stand_straight", "Stand straight", "කෙළින් සිටගන්න", "straight", "down", "front", "standing"),
    ("turn_around", "Turn around", "වටයකට හැරෙන්න", "upright", "down", "back", "standing"),
    ("sit_down", "Sit down", "වාඩිවෙන්න", "upright", "down", "front", "seated"),
)
DESTINATION_COMMANDS = (
    ("run_to_wall", "Run to the wall", "බිත්තිය ළඟට දුවන්න", "wall-zone"),
    ("run_to_blackboard", "Run to the blackboard", "කළුලෑල්ල ළඟට දුවන්න", "blackboard-zone"),
)
MISCONCEPTIONS = (
    "verb_action_semantic_confusion",
    "bend_vs_sit_confusion",
    "stand_vs_sit_confusion",
    "stretch_vs_arms_down_confusion",
    "turn_vs_move_confusion",
    "body_part_or_arm_reference_confusion",
    "wall_vs_blackboard_noun_confusion",
    "destination_ignored",
    "run_command_treated_as_stationary_action",
    "landmark_visual_identification_confusion",
    "return_to_origin_concept_confusion",
    "come_back_treated_as_any_movement",
    "origin_not_retained",
    "stops_before_origin",
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
        "G5-ENG-BEH-POSTURE-01",
        "action_mirror",
        "ශරීර ඉරියව් සඳහා ඉංග්‍රීසි උපදෙස්",
        "easy-medium",
        "body_state",
    ),
    AtomicSkill(
        "G5-ENG-BEH-DESTINATION-01",
        "classroom_dash",
        "පන්ති කාමරයේ ස්ථානයකට යන ඉංග්‍රීසි උපදෙස්",
        "medium",
        "classroom_navigation",
    ),
    AtomicSkill(
        "G5-ENG-BEH-RETURN-01",
        "come_back",
        "Come back යන උපදෙස තේරුම් ගැනීම",
        "medium-hard",
        "classroom_navigation",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class ClassroomActionItem:
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


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> ClassroomActionItem:
    """The same command game with two choices: the commanded action or place and one other."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    game = dict(item.game_data)
    rng = _rng(skill_id, "simpler", seed)
    if game["response_kind"] == "body_state":
        field, target = "allowed_interaction_ids", str(game["command_id"])
    else:
        field, target = "allowed_destination_ids", str(game["target_location_id"])
    choices = [str(value) for value in game[field]]  # type: ignore[union-attr]
    kept = {target, rng.choice([value for value in choices if value != target])}
    game[field] = [value for value in choices if value in kept]
    stem, _, version = item.revision_id.rpartition("@")
    return replace(item, game_data=game, revision_id=f"{stem}:simpler@{version}")


def generate_item(skill_id: str, *, role: str, seed: int) -> ClassroomActionItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("CLASSROOM_ACTION_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    command_token = hashlib.sha256(f"{skill_id}:{role}:{seed}:command".encode()).hexdigest()[:16]
    if skill.chapter == "action_mirror":
        command = rng.choice(BODY_COMMANDS)
        action_id, command_en, _translation, posture, arms, orientation, seat = command
        game: dict[str, object] = {
            "response_kind": "body_state",
            "activity_id": "action_mirror",
            "command_id": action_id,
            "command_token": command_token,
            "command_text_en": command_en,
            "scene_variant": f"mirror-{seed % 3}",
            "character_start_state": {
                "posture": "upright",
                "arm_position": "down",
                "orientation": "front",
                "seat_state": "standing",
            },
            "allowed_interaction_ids": [row[0] for row in BODY_COMMANDS],
            "target_body_state": {
                "posture": posture,
                "arm_position": arms,
                "orientation": orientation,
                "seat_state": seat,
            },
        }
        prompt = "ඉංග්‍රීසි උපදෙස බලා දරුවාගේ ඉරියව්ව සකස් කරන්න."
    elif skill.chapter == "classroom_dash":
        command_id, command_en, _translation, target = rng.choice(DESTINATION_COMMANDS)
        game = {
            "response_kind": "classroom_navigation",
            "activity_id": "classroom_dash",
            "command_id": command_id,
            "command_token": command_token,
            "command_text_en": command_en,
            "scene_variant": f"dash-{seed % 3}",
            "origin_id": "start-a",
            "character_start_location": "start-a",
            "allowed_destination_ids": ["wall-zone", "blackboard-zone", "start-a"],
            "target_location_id": target,
        }
        prompt = "ඉංග්‍රීසි උපදෙස බලා දරුවා නිවැරදි තැනට ගෙන යන්න."
    else:
        start = rng.choice(("wall-zone", "blackboard-zone"))
        game = {
            "response_kind": "classroom_navigation",
            "activity_id": "come_back",
            "command_id": "come_back",
            "command_token": command_token,
            "command_text_en": "Come back",
            "scene_variant": f"return-{seed % 3}",
            "origin_id": "start-a",
            "character_start_location": start,
            "allowed_destination_ids": ["wall-zone", "blackboard-zone", "start-a"],
            "target_location_id": "start-a",
        }
        prompt = "ඉංග්‍රීසි උපදෙස බලා දරුවා ආරම්භක තැනට ගෙන එන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return ClassroomActionItem(
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


def _public_game(game: Mapping[str, object]) -> dict[str, object]:
    hidden = {"command_id", "target_body_state", "target_location_id"}
    return {key: value for key, value in game.items() if key not in hidden}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    if game["response_kind"] == "body_state":
        return {
            "kind": "body_state",
            "command_id": str(game["command_token"]),
            "final_body_state": dict(game["target_body_state"]),  # type: ignore[arg-type]
            "semantic_action_id": str(game["command_id"]),
            "interaction_trace": [f"pose:{game['command_id']}"],
            "revisions": 0,
        }
    target = str(game["target_location_id"])
    return {
        "kind": "classroom_navigation",
        "command_id": str(game["command_token"]),
        "origin_id": str(game["origin_id"]),
        "movement_path": [{"sequence": 1, "action": "move", "destination_id": target}],
        "final_location_id": target,
        "interaction_trace": [f"move:{target}"],
        "revisions": 0,
        "invalid_drops": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | ClassroomActionItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, ClassroomActionItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_CLASSROOM_ACTION_ITEM")
    expected = correct_response(game)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    if set(response) != set(expected):
        raise ValueError("MALFORMED_CLASSROOM_ACTION_RESPONSE")
    if response.get("command_id") != game["command_token"]:
        raise ValueError("STALE_CLASSROOM_ACTION_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(x, str) for x in trace):
        raise ValueError("INVALID_CLASSROOM_ACTION_TRACE")
    normalized = dict(response)
    if kind == "body_state":
        state = response.get("final_body_state")
        if not isinstance(state, Mapping) or set(state) != {
            "posture",
            "arm_position",
            "orientation",
            "seat_state",
        }:
            raise ValueError("INVALID_BODY_STATE")
        allowed = {
            "posture": {"upright", "straight", "bent"},
            "arm_position": {"down", "stretched"},
            "orientation": {"front", "back"},
            "seat_state": {"standing", "seated"},
        }
        if any(state[key] not in values for key, values in allowed.items()):
            raise ValueError("INVALID_BODY_STATE_ENUM")
        target = game["target_body_state"]
        correct = state == target and response.get("semantic_action_id") == game["command_id"]
        selected = str(response.get("semantic_action_id"))
        command = str(game["command_id"])
        error = (
            "bend_vs_sit_confusion"
            if {selected, command} == {"bend", "sit_down"}
            else "stand_vs_sit_confusion"
            if {selected, command} == {"stand_straight", "sit_down"}
            else "stretch_vs_arms_down_confusion"
            if {selected, command} == {"stretch_arms", "arms_down"}
            else "turn_vs_move_confusion"
            if command == "turn_around"
            else "verb_action_semantic_confusion"
        )
        return correct, "correct" if correct else error, normalized
    path = response.get("movement_path")
    if not isinstance(path, list) or not path or not all(isinstance(row, Mapping) for row in path):
        raise ValueError("INVALID_CLASSROOM_MOVEMENT_PATH")
    allowed_destinations = set(game["allowed_destination_ids"])  # type: ignore[arg-type]
    if response.get("final_location_id") not in allowed_destinations:
        raise ValueError("INVALID_CLASSROOM_DESTINATION")
    if response.get("origin_id") != game["origin_id"]:
        raise ValueError("INVALID_CLASSROOM_ORIGIN")
    target = str(game["target_location_id"])
    final = str(response["final_location_id"])
    correct = final == target
    if game["command_id"] == "come_back":
        error = (
            "correct"
            if correct
            else (
                "stops_before_origin"
                if final not in {"wall-zone", "blackboard-zone"}
                else "return_to_origin_concept_confusion"
            )
        )
    else:
        error = (
            "correct"
            if correct
            else (
                "wall_vs_blackboard_noun_confusion"
                if final in {"wall-zone", "blackboard-zone"}
                else "destination_ignored"
            )
        )
    return correct, error, normalized


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
    command = str(game["command_text_en"])
    if scaffold_type == "visual_guidance":
        if game["response_kind"] == "body_state":
            return [f"‘{command}’ කියවන විට ශරීරයේ වෙනස් විය යුතු කොටස බලන්න."]
        if game["command_id"] == "come_back":
            return ["ආරම්භ කළ වර්ණවත් පැදුර මතක තබාගන්න."]
        return ["උපදෙසේ අවසාන ස්ථාන වචනය සහ පන්ති කාමරයේ ස්ථානය සසඳන්න."]
    if game["response_kind"] == "body_state":
        return [
            f"ඉංග්‍රීසි උපදෙස කියවමු: {command}.",
            "ක්‍රියා වචනයට අදාළ ශරීර කොටස හඳුනාගනිමු.",
            "ඉරියව්ව වෙනස් කර නැවත උපදෙස සමඟ සසඳමු.",
        ]
    if game["command_id"] == "come_back":
        return [
            "දරුවා දැන් සිටින තැන බලමු.",
            "දරුවා මුලින් සිටි පැදුර සොයමු.",
            "දරුවා නැවත එම ආරම්භක තැනට ගෙන එමු.",
        ]
    return [
        f"ඉංග්‍රීසි උපදෙස කියවමු: {command}.",
        "අවසානයේ සඳහන් පන්ති කාමර ස්ථානය සොයමු.",
        "දරුවා එම ස්ථානයට ගෙන යමු.",
    ]


def public_game_data(item: ClassroomActionItem) -> dict[str, object]:
    return {"chapter": item.chapter, **_public_game(item.game_data)}


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "area": AREA_ID,
                "version": PACKAGE_VERSION,
                "skills": [skill.skill_id for skill in ATOMIC_SKILLS],
                "commands": [row[0] for row in BODY_COMMANDS + DESTINATION_COMMANDS],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
