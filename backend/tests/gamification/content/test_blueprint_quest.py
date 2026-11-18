import pytest

from app.gamification.content.blueprint_quest import (
    BLOCKED_TERMS,
    PHRASE_FORMS,
    SOURCE_ENTRIES,
    correct_response,
    generate_item,
    public_game_data,
    validate_constructed_response,
)


def test_source_and_blocks():
    assert len(SOURCE_ENTRIES)==20 and BLOCKED_TERMS==("Shrine room","Sick room") and "Living Room" in PHRASE_FORMS
@pytest.mark.parametrize("skill",["G5-ENG-PLACE-VOCAB-01","G5-ENG-PLACE-GROUP-02","G5-ENG-PLACE-NAME-03"])
def test_public_strips_answers_and_server_scores(skill):
    item=generate_item(skill,role="unsupported_before",seed=3); public=public_game_data(item)
    assert "target_mapping" not in public and "target_sequence" not in public
    assert validate_constructed_response(item,correct_response(item.game_data))[0]
