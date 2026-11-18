import pytest

from app.gamification.content.transit_terminal_quest import (
    EXCLUDED_UNTIL_RENDERER_REVIEW,
    SKILLS,
    correct_response,
    generate_item,
    public_game_data,
    validate_constructed_response,
)


def test_transport_items_are_answer_free_and_exclude_ambiguous_vehicles() -> None:
    for seed in (0, 1, 2):
        item = generate_item("G5-ENG-TRANSPORT-VOCAB-01", role="unsupported_before", seed=seed)
        after = generate_item("G5-ENG-TRANSPORT-VOCAB-01", role="unsupported_after", seed=seed)
        public = public_game_data(item)
        rendered = repr(public)
        assert "target_mapping" not in public
        assert len(public["words"]) == len(public["vehicles"]) == len(after.game_data["target_mapping"])
        for form in (*EXCLUDED_UNTIL_RENDERER_REVIEW, "truck", "airplane", "bike"):
            assert form not in rendered
        assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")
    assert len(SKILLS) == 1


def test_duplicate_vehicle_target_is_rejected() -> None:
    item = generate_item("G5-ENG-TRANSPORT-VOCAB-01", role="unsupported_before", seed=1)
    response = correct_response(item.game_data)
    response["placements"][1]["vehicle_token"] = response["placements"][0]["vehicle_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_TRANSPORT_MAPPING"):
        validate_constructed_response(item, response)
