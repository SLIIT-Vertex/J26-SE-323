import pytest

from app.gamification.content.wildlife_ranger import (
    MISCONCEPTIONS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_all_wildlife_skills_are_answer_free_and_score_server_side() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=31)
        public = public_game_data(item)
        assert "target_mapping" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_unreviewed_source_anomalies_are_not_active_content() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=7)
        public_text = repr(public_game_data(item))
        assert "Shake" not in public_text
        assert "Rattle Snake" not in public_text
        assert "Humming bird" not in public_text


def test_duplicate_wildlife_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-ANIMAL-VOCAB-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["entry_token"] = response["placements"][0]["entry_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_WILDLIFE_MAPPING"):
        validate_constructed_response(item, response)


def test_wildlife_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("animal_word_visual_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
