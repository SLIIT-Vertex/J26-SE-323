import pytest

from app.gamification.content.rainbow_wardrobe_quest import (
    EXCLUDED_PENDING_REVIEW,
    MISCONCEPTIONS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_wardrobe_item_is_answer_free_and_server_scored() -> None:
    item = generate_item("G5-ENG-CLOTHES-VOCAB-01", role="unsupported_before", seed=31)
    public = public_game_data(item)
    assert "target_mapping" not in public
    assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")


def test_handkerchief_is_transcribed_but_not_active() -> None:
    assert EXCLUDED_PENDING_REVIEW == ("Handkerchief",)
    for seed in range(12):
        item = generate_item("G5-ENG-CLOTHES-VOCAB-01", role="unsupported_before", seed=seed)
        assert "Handkerchief" not in repr(public_game_data(item))


def test_duplicate_clothes_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-CLOTHES-VOCAB-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["word_token"] = response["placements"][0]["word_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_CLOTHES_MAPPING"):
        validate_constructed_response(item, response)


def test_clothes_belief_normalizes_with_unknown_fallback() -> None:
    belief = infer_belief("not-in-catalogue")
    assert belief["predicted_label"] == "unknown_or_other"
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
