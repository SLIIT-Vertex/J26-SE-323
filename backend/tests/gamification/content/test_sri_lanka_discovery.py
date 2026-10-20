import pytest

from app.gamification.content.sri_lanka_discovery import (
    MISCONCEPTIONS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_each_skill_has_answer_free_public_item_and_valid_response() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=21)
        public = public_game_data(item)
        assert "target_mapping" not in public
        assert "target_groups" not in public
        assert "correct" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_before_and_after_are_distinct_revisions() -> None:
    before = generate_item(next(iter(SKILLS)), role="unsupported_before", seed=7)
    after = generate_item(next(iter(SKILLS)), role="unsupported_after", seed=8)
    assert before.revision_id != after.revision_id
    assert before.game_data["command_token"] != after.game_data["command_token"]


def test_duplicate_label_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-SL-VOCAB-RECOGNITION-01", role="unsupported_before", seed=3)
    response = correct_response(item.game_data)
    response["placements"][1]["label_id"] = response["placements"][0]["label_id"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_LABEL_MAPPING"):
        validate_constructed_response(item, response)


def test_wrong_group_is_structured_evidence() -> None:
    item = generate_item("G5-ENG-SL-CULTURAL-GROUP-01", role="unsupported_before", seed=4)
    response = correct_response(item.game_data)
    first = response["groups"][0]["ordered_member_ids"].pop()
    response["groups"][1]["ordered_member_ids"].append(first)
    correct, error, _ = validate_constructed_response(item, response)
    assert correct is False
    assert error == "place_vs_cultural_object_confusion"


def test_belief_is_normalized_and_retains_unknown() -> None:
    belief = infer_belief("national_category_vs_exemplar_confusion")
    probabilities = belief["probabilities"]
    assert set(probabilities) == set(MISCONCEPTIONS)
    assert abs(sum(probabilities.values()) - 1.0) < 1e-9
    assert "unknown_or_other" in probabilities
