import pytest

from app.gamification.content.everyday_object_quest import (
    MISCONCEPTIONS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_all_object_skills_are_answer_free_and_server_scored() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=31)
        public = public_game_data(item)
        assert "target_mapping" not in public
        assert "target_sequence" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_unresolved_hole_puncture_is_not_active() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=7)
        assert "Hole Puncture" not in repr(public_game_data(item))


def test_duplicate_object_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-OBJECT-VOCAB-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["word_token"] = response["placements"][0]["word_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_OBJECT_MAPPING"):
        validate_constructed_response(item, response)


def test_object_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("object_word_visual_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
