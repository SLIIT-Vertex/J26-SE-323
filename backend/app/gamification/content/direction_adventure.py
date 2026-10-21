"""Grade 5 Sinhala direction-compass and child-centred place activities."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-14"
UNIVERSAL_SKILL_ID = "MAT-DIR"
PACKAGE_VERSION = "g5-mat-direction-adventure-v1"
CATALOGUE_VERSION = "g5-mat-direction-misconceptions-v1"
FEATURE_VERSION = "g5-mat-direction-features-v1"
MAPPING_VERSION = "g5-mat-direction-source-mapping-v1"
MODEL_VERSION = "g5-mat-direction-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-direction-deterministic-support-v1"
SCORING_VERSION = "g5-mat-direction-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-direction-parallel-v1"

Chapter = Literal["main_direction_compass", "secondary_direction_compass", "place_direction_scene"]
Direction = Literal["north", "north_east", "east", "south_east", "south", "south_west", "west", "north_west"]

MAIN_POSITIONS = ("top", "right", "bottom", "left")
SECONDARY_POSITIONS = ("top_right", "bottom_right", "bottom_left", "top_left")
ALL_DIRECTIONS: tuple[Direction, ...] = (
    "north", "north_east", "east", "south_east", "south", "south_west", "west", "north_west",
)
POSITION_DIRECTIONS = {
    "top": "north", "top_right": "north_east", "right": "east", "bottom_right": "south_east",
    "bottom": "south", "bottom_left": "south_west", "left": "west", "top_left": "north_west",
}
PLACES = (
    "dagoba", "mango_tree", "house", "school", "shop", "gate", "coconut_tree", "post_office",
)
PLACE_LABELS = {
    "dagoba": "චෛත්‍යය", "mango_tree": "අඹ ගස", "house": "නිවස", "school": "පාසල",
    "shop": "වෙළඳසැල", "gate": "ගේට්ටුව", "coconut_tree": "පොල් ගස", "post_office": "තැපැල් කාර්යාලය",
}
MISCONCEPTIONS = (
    "north_south_reversal", "east_west_reversal", "screen_left_as_east", "secondary_on_main_axis",
    "correct_labels_wrong_positions", "incomplete_compass", "main_on_secondary_axis", "north_east_north_west_reversal",
    "south_east_south_west_reversal", "single_component_direction", "child_viewpoint_reversal",
    "adjacent_diagonal_confusion", "direction_for_wrong_place", "invalid_scene_evidence", "unknown_or_other",
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
    AtomicSkill("G5-MAT-DIRECTION-MAIN-01", "main_direction_compass", "ප්‍රධාන දිශා තෝරමු", "easy", "main_direction_compass"),
    AtomicSkill("G5-MAT-DIRECTION-SECONDARY-01", "secondary_direction_compass", "අනු දිශා තෝරමු", "easy-medium", "secondary_direction_compass"),
    AtomicSkill("G5-MAT-DIRECTION-SCENE-01", "place_direction_scene", "ස්ථානය කියමු", "medium-hard", "place_direction_scene"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class DirectionItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Literal["unsupported_before", "unsupported_after"]
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _scene(seed: int, role: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = _rng("scene", role, seed)
    shift = 0 if role == "unsupported_before" else rng.randint(1, 7)
    places = list(PLACES[shift:] + PLACES[:shift])
    placements = [
        {"place_id": place, "direction": direction, "label_si": PLACE_LABELS[place]}
        for place, direction in zip(places, ALL_DIRECTIONS, strict=True)
    ]
    templates = (
        "ළමයාට ___ දෙසින් {place} තිබේ.",
        "ළමයාට ___ දෙසින් {place} තිබේ.",
        "ළමයා {place} වෙත යා යුත්තේ ___ දෙසටයි.",
        "{place} ළමයාට ___ දෙසින් තිබේ.",
    )
    statements = [
        {
            "statement_id": f"statement-{index + 1}",
            "place_id": row["place_id"],
            "template_si": templates[index % len(templates)].format(place=row["label_si"]),
        }
        for index, row in enumerate(placements)
    ]
    return placements, statements


SIMPLER_POSITION_COUNT = 2
MAIN_DIRECTIONS = ("north", "east", "south", "west")


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> DirectionItem:
    """The same direction skill with two compass points, or only the main directions in a scene."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> DirectionItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("DIRECTION_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    pick = random.Random(f"{skill_id}:simpler:{seed}")
    if skill.response_kind == "main_direction_compass":
        game: dict[str, object] = {
            "response_kind": skill.response_kind,
            "active_positions": sorted(pick.sample(MAIN_POSITIONS, SIMPLER_POSITION_COUNT), key=MAIN_POSITIONS.index) if simpler else list(MAIN_POSITIONS),
            "direction_options": ["north", "east", "south", "west"],
        }
        prompt = "මාලිමාවේ ප්‍රධාන දිශා හතර නිවැරදි තැන්වල තෝරන්න."
    elif skill.response_kind == "secondary_direction_compass":
        game = {
            "response_kind": skill.response_kind,
            "active_positions": sorted(pick.sample(SECONDARY_POSITIONS, SIMPLER_POSITION_COUNT), key=SECONDARY_POSITIONS.index) if simpler else list(SECONDARY_POSITIONS),
            "anchor_directions": ["north", "east", "south", "west"],
            "direction_options": ["north_east", "south_east", "south_west", "north_west"],
        }
        prompt = "ප්‍රධාන දිශා දෙක අතර ඇති අනු දිශාව තෝරන්න."
    else:
        placements, statements = _scene(seed, role)
        if simpler:
            # The whole scene stays; the child names only the places in the four main directions.
            main_places = {row["place_id"] for row in placements if row["direction"] in MAIN_DIRECTIONS}
            statements = [row for row in statements if row["place_id"] in main_places]
        scene_digest = hashlib.sha256(json.dumps(placements, sort_keys=True).encode()).hexdigest()[:12]
        game = {
            "response_kind": skill.response_kind, "scene_id": f"scene-{scene_digest}",
            "placements": placements, "statements": statements, "direction_options": list(ALL_DIRECTIONS),
        }
        prompt = "ළමයා සිටින තැනින් බලමින් එක් එක් ස්ථානයේ දිශාව තෝරන්න."
    revision = f"{skill_id}:{role}{':simpler' if simpler else ''}:{seed % 100000}@v1"
    return DirectionItem(
        f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role,
        prompt, (), "constructed-response", {}, game,
    )


def _expected_selections(game: Mapping[str, object]) -> list[dict[str, str]]:
    kind = str(game["response_kind"])
    if kind in {"main_direction_compass", "secondary_direction_compass"}:
        return [
            {"position": position, "direction": POSITION_DIRECTIONS[position]}
            for position in game["active_positions"]  # type: ignore[union-attr]
        ]
    placement_by_place = {row["place_id"]: row["direction"] for row in game["placements"]}  # type: ignore[index,union-attr]
    return [
        {
            "statement_id": row["statement_id"], "place_id": row["place_id"],
            "selected_direction": placement_by_place[row["place_id"]],
        }
        for row in game["statements"]  # type: ignore[union-attr]
    ]


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    selections = _expected_selections(game)
    if kind == "secondary_direction_compass":
        return {"kind": kind, "anchor_directions_seen": list(game["anchor_directions"]), "selections": selections, "selection_order": list(game["active_positions"])}
    if kind == "main_direction_compass":
        return {"kind": kind, "selections": selections, "selection_order": list(game["active_positions"])}
    return {"kind": kind, "scene_id": game["scene_id"], "selections": selections, "selection_order": [row["statement_id"] for row in selections], "revisions": 0}


def _is_unique_string_list(value: object, expected: set[str]) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value) and len(value) == len(set(value)) and set(value) == expected


def _opposite(direction: str) -> str:
    index = ALL_DIRECTIONS.index(direction)  # type: ignore[arg-type]
    return ALL_DIRECTIONS[(index + 4) % 8]


def validate_scene(game: Mapping[str, object]) -> None:
    placements, statements = game.get("placements"), game.get("statements")
    if not isinstance(placements, list) or len(placements) != 8 or not all(isinstance(row, Mapping) for row in placements):
        raise ValueError("AMBIGUOUS_DIRECTION_SCENE")
    place_ids = [str(row.get("place_id")) for row in placements]
    directions = [str(row.get("direction")) for row in placements]
    if set(place_ids) != set(PLACES) or len(set(place_ids)) != 8 or set(directions) != set(ALL_DIRECTIONS) or len(set(directions)) != 8:
        raise ValueError("AMBIGUOUS_DIRECTION_SCENE")
    # Every place stays in the scene; the simpler version asks about only some of them.
    if not isinstance(statements, list) or not 1 <= len(statements) <= 8 or not all(isinstance(row, Mapping) for row in statements):
        raise ValueError("AMBIGUOUS_DIRECTION_SCENE")
    asked = [str(row.get("place_id")) for row in statements]
    if len(set(asked)) != len(asked) or not set(asked) <= set(PLACES):
        raise ValueError("AMBIGUOUS_DIRECTION_SCENE")


def validate_constructed_response(item: Mapping[str, object] | DirectionItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, DirectionItem) else item["game_data"]
    assert isinstance(game, Mapping)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    selections = response.get("selections")
    if not isinstance(selections, list) or not all(isinstance(row, Mapping) for row in selections):
        raise ValueError("INVALID_DIRECTION_RESPONSE")
    expected = _expected_selections(game)
    normalized = dict(response)
    if kind in {"main_direction_compass", "secondary_direction_compass"}:
        required = set(game["active_positions"])  # type: ignore[arg-type]
        if len(selections) != len(required) or any(set(row) != {"position", "direction"} for row in selections):
            raise ValueError("INVALID_DIRECTION_RESPONSE")
        positions = [str(row["position"]) for row in selections]
        selected_directions = [str(row["direction"]) for row in selections]
        if (
            set(positions) != required
            or len(set(positions)) != len(required)
            or any(direction not in ALL_DIRECTIONS for direction in selected_directions)
            or not _is_unique_string_list(response.get("selection_order"), required)
        ):
            raise ValueError("INVALID_DIRECTION_RESPONSE")
        if kind == "secondary_direction_compass" and response.get("anchor_directions_seen") != game["anchor_directions"]:
            raise ValueError("INVALID_DIRECTION_RESPONSE")
        expected_by_position = {row["position"]: row["direction"] for row in expected}
        first = next((row for row in selections if row["direction"] != expected_by_position[row["position"]]), None)
        if first is None:
            return True, "correct", normalized
        position, selected, wanted = str(first["position"]), str(first["direction"]), str(expected_by_position[first["position"]])
        normalized["_feedback_column"] = position
        if kind == "main_direction_compass":
            if selected not in {"north", "east", "south", "west"}: error = "secondary_on_main_axis"
            elif {selected, wanted} == {"north", "south"}: error = "north_south_reversal"
            elif {selected, wanted} == {"east", "west"}: error = "screen_left_as_east" if position == "left" and selected == "east" else "east_west_reversal"
            else: error = "correct_labels_wrong_positions"
        else:
            if selected in {"north", "east", "south", "west"}: error = "main_on_secondary_axis"
            elif {selected, wanted} == {"north_east", "north_west"}: error = "north_east_north_west_reversal"
            elif {selected, wanted} == {"south_east", "south_west"}: error = "south_east_south_west_reversal"
            else: error = "correct_labels_wrong_positions"
        return False, error, normalized

    validate_scene(game)
    if response.get("scene_id") != game.get("scene_id") or type(response.get("revisions")) is not int or not 0 <= response["revisions"] <= 100:
        raise ValueError("INVALID_SCENE_EVIDENCE")
    statement_ids = {str(row["statement_id"]) for row in expected}
    if len(selections) != len(expected) or any(set(row) != {"statement_id", "place_id", "selected_direction"} for row in selections):
        raise ValueError("INVALID_SCENE_EVIDENCE")
    if any(
        str(row["place_id"]) not in PLACES or str(row["selected_direction"]) not in ALL_DIRECTIONS
        for row in selections
    ):
        raise ValueError("INVALID_SCENE_EVIDENCE")
    if not _is_unique_string_list(response.get("selection_order"), statement_ids):
        raise ValueError("INVALID_SCENE_EVIDENCE")
    expected_by_statement = {row["statement_id"]: row for row in expected}
    seen = {str(row["statement_id"]) for row in selections}
    if seen != statement_ids or len(seen) != len(expected):
        raise ValueError("INVALID_SCENE_EVIDENCE")
    first = next((row for row in selections if row.get("place_id") != expected_by_statement.get(row.get("statement_id"), {}).get("place_id") or row.get("selected_direction") != expected_by_statement.get(row.get("statement_id"), {}).get("selected_direction")), None)
    if first is None:
        return True, "correct", normalized
    statement_id = str(first.get("statement_id"))
    normalized["_feedback_column"] = statement_id
    expected_row = expected_by_statement.get(statement_id, {})
    selected, wanted = str(first.get("selected_direction")), str(expected_row.get("selected_direction"))
    if first.get("place_id") != expected_row.get("place_id"): error = "direction_for_wrong_place"
    elif wanted in ALL_DIRECTIONS and selected == _opposite(wanted): error = "child_viewpoint_reversal"
    else: error = "adjacent_diagonal_confusion"
    return False, error, normalized


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = .8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(.72, max(.2, evidence_quality * .72))
    other = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else other for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = str(game["response_kind"])
    if scaffold_type == "visual_guidance":
        return {
            "main_direction_compass": ["සිරස් සහ තිරස් මාලිමා රේඛා දෙස බලන්න."],
            "secondary_direction_compass": ["වැරදුණු අනු දිශාව දෙපස ඇති ප්‍රධාන දිශා දෙක බලන්න."],
            "place_direction_scene": ["ළමයාගෙන් පටන්ගෙන වාක්‍යයේ ස්ථානය දක්වා ඇති ඊතලය බලන්න."],
        }[kind]
    if kind == "main_direction_compass":
        return ["ඉහළට උතුර තබමු.", "උතුරට විරුද්ධව දකුණ තබමු.", "දකුණතට නැගෙනහිරත් වමට බස්නාහිරත් තබමු."]
    if kind == "secondary_direction_compass":
        return ["අනු දිශාවට අසල ප්‍රධාන දිශා දෙක එක් කරමු.", "ඉහළ-දකුණ ඊසානයි; පහළ-දකුණ ගිනිකොණයි.", "පහළ-වම නිරිතයි; ඉහළ-වම වයඹයි."]
    return ["ළමයා මධ්‍යයේ සිටින බව බලමු.", "ළමයාගෙන් ස්ථානය වෙත ඊතලය අනුගමනය කරමු.", "එම ඊතලයට ගැළපෙන දිශාව වාක්‍යයේ තෝරමු."]


def package_hash() -> str:
    payload = {"area_id": AREA_ID, "package_version": PACKAGE_VERSION, "skills": [skill.skill_id for skill in ATOMIC_SKILLS], "directions": ALL_DIRECTIONS, "places": PLACES}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
