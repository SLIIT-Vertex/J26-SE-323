from copy import deepcopy

import pytest

from app.gamification.content.direction_adventure import (
    ALL_DIRECTIONS,
    ATOMIC_SKILLS,
    MAIN_POSITIONS,
    MISCONCEPTIONS,
    PLACES,
    SECONDARY_POSITIONS,
    correct_response,
    generate_item,
    infer_belief,
    validate_constructed_response,
    validate_scene,
)


def test_direction_package_has_exactly_three_activities_in_two_games():
    assert [skill.response_kind for skill in ATOMIC_SKILLS] == [
        "main_direction_compass", "secondary_direction_compass", "place_direction_scene",
    ]


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_every_direction_response_is_server_scored(skill):
    item = generate_item(skill.skill_id, role="unsupported_before", seed=14)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_primary_and_secondary_compass_positions_follow_textbook_arrangement():
    main = generate_item("G5-MAT-DIRECTION-MAIN-01", role="unsupported_before", seed=1)
    secondary = generate_item("G5-MAT-DIRECTION-SECONDARY-01", role="unsupported_before", seed=1)
    assert main.game_data["active_positions"] == list(MAIN_POSITIONS)
    assert correct_response(main.game_data)["selections"] == [
        {"position": "top", "direction": "north"}, {"position": "right", "direction": "east"},
        {"position": "bottom", "direction": "south"}, {"position": "left", "direction": "west"},
    ]
    assert secondary.game_data["active_positions"] == list(SECONDARY_POSITIONS)
    assert correct_response(secondary.game_data)["selections"][0] == {"position": "top_right", "direction": "north_east"}


def test_scene_uses_every_place_and_direction_once_and_rotates_equivalently():
    before = generate_item("G5-MAT-DIRECTION-SCENE-01", role="unsupported_before", seed=9)
    after = generate_item("G5-MAT-DIRECTION-SCENE-01", role="unsupported_after", seed=9)
    validate_scene(before.game_data); validate_scene(after.game_data)
    assert {row["place_id"] for row in before.game_data["placements"]} == set(PLACES)
    assert {row["direction"] for row in before.game_data["placements"]} == set(ALL_DIRECTIONS)
    assert before.game_data["placements"] != after.game_data["placements"]
    assert before.parallel_family_id == after.parallel_family_id
    assert before.revision_id != after.revision_id


def test_scene_rejects_duplicate_or_ambiguous_positions():
    item = generate_item("G5-MAT-DIRECTION-SCENE-01", role="unsupported_before", seed=2)
    game = deepcopy(item.game_data)
    game["placements"][1]["direction"] = game["placements"][0]["direction"]
    with pytest.raises(ValueError, match="AMBIGUOUS_DIRECTION_SCENE"):
        validate_scene(game)


def test_child_viewpoint_reversal_and_full_probability_distribution():
    item = generate_item("G5-MAT-DIRECTION-SCENE-01", role="unsupported_before", seed=3)
    response = correct_response(item.game_data)
    response["selections"][0]["selected_direction"] = "south"
    correct, error, normalized = validate_constructed_response(item, response)
    assert correct is False and error == "child_viewpoint_reversal"
    assert normalized["_feedback_column"] == "statement-1"
    belief = infer_belief(error)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1)


def test_public_game_data_never_contains_explicit_answer_map():
    for skill in ATOMIC_SKILLS:
        item = generate_item(skill.skill_id, role="unsupported_before", seed=5)
        assert "correct_response" not in item.game_data
        assert "answers" not in item.game_data
