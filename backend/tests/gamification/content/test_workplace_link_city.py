import pytest

from app.gamification.content.workplace_link_city import (
    EXCLUDED_PENDING_INCLUSION_REVIEW,
    PAIRS,
    correct_response,
    generate_item,
    public_game_data,
    validate_constructed_response,
)


def test_exact_pairs_shared_buildings_and_exclusion() -> None:
    assert ("Fisherman", "Sea") in EXCLUDED_PENDING_INCLUSION_REVIEW
    buildings = [row for row in PAIRS if row[3] == "Buildings"]
    assert [row[1] for row in buildings] == ["Electrician", "Mason"]
    assert any(row[1] == "Fish monger" and row[3] == "Fish Stall" for row in PAIRS)


@pytest.mark.parametrize("skill_id", ["G5-ENG-WORK-VOCAB-01", "G5-ENG-WORK-PLACE-02"])
def test_public_items_strip_server_answers_and_score(skill_id: str) -> None:
    item = generate_item(skill_id, role="unsupported_before", seed=3)
    public = public_game_data(item)
    assert "target_mapping" not in public and "target_links" not in public
    assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")


def test_many_to_one_buildings_links_are_valid_but_unknown_tokens_are_rejected() -> None:
    item = generate_item("G5-ENG-WORK-PLACE-02", role="unsupported_before", seed=3)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[0]
    response["links"][0]["place_token"] = "p-unknown"
    with pytest.raises(ValueError, match="INVALID_WORKPLACE_LINK_TOKEN_OR_SEQUENCE"):
        validate_constructed_response(item, response)
