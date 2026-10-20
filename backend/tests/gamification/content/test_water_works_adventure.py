import pytest

from app.gamification.content.water_works_adventure import (
    ACTIONS,
    MISCONCEPTIONS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_water_action_is_answer_free_and_server_scored() -> None:
    for seed in (0, 1, 2):
        item = generate_item("G5-ENG-WATER-ACTION-01", role="unsupported_before", seed=seed)
        after = generate_item("G5-ENG-WATER-ACTION-01", role="unsupported_after", seed=seed)
        public = public_game_data(item)
        assert "target_mapping" not in public
        assert len(public["actions"]) == len(public["scenes"]) == len(after.game_data["target_mapping"])
        assert "Water the plants" not in repr(public)
        assert "Water (the plants)" in repr(public) or item.chapter != "splash_detective"
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")
    assert len(SKILLS) == 1
    assert {row[1] for row in ACTIONS} == {"Bathe", "Cook", "Wash", "Drink", "Water (the plants)"}


def test_duplicate_water_scene_is_rejected() -> None:
    item = generate_item("G5-ENG-WATER-ACTION-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["scene_token"] = response["placements"][0]["scene_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_WATER_MAPPING"):
        validate_constructed_response(item, response)


def test_water_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("bathe_wash_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
    sparse = infer_belief("not-a-label", sparse=True)
    assert sparse["predicted_label"] == "unknown_or_other"
    assert sparse["fallback_used"] is True
