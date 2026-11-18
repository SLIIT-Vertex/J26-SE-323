import pytest

from app.gamification.content.bloom_builder_garden import (
    FLOWERS,
    STAGES,
    correct_response,
    generate_item,
    public_game_data,
    validate_constructed_response,
)


def test_exact_source_forms_and_all_difficulty_stages() -> None:
    assert [row[1] for row in FLOWERS] == ["Marigold", "Shoe flower", "Rose", "Sunflower", "Jasmine"]
    assert [generate_item("G5-ENG-FLOWER-VOCAB-01", role="unsupported_before", seed=seed).chapter for seed in range(3)] == [stage[0] for stage in STAGES]


def test_public_flower_item_strips_answer_and_scores_on_server() -> None:
    item = generate_item("G5-ENG-FLOWER-VOCAB-01", role="unsupported_before", seed=2)
    assert "target_mapping" not in public_game_data(item)
    assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")


def test_unknown_and_duplicate_flower_tokens_are_rejected() -> None:
    item = generate_item("G5-ENG-FLOWER-VOCAB-01", role="unsupported_before", seed=1)
    response = correct_response(item.game_data)
    response["placements"][0]["flower_token"] = "f-unknown"
    with pytest.raises(ValueError, match="INVALID_FLOWER_MAPPING_TOKEN_OR_SEQUENCE"):
        validate_constructed_response(item, response)
    response = correct_response(item.game_data)
    response["placements"][1]["word_token"] = response["placements"][0]["word_token"]
    with pytest.raises(ValueError):
        validate_constructed_response(item, response)
