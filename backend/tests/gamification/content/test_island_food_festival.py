import pytest

from app.gamification.content.island_food_festival import (
    MISCONCEPTIONS,
    SKILLS,
    UNRESOLVED_SOURCE_FORMS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_all_food_skills_are_answer_free_and_server_scored() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=31)
        public = public_game_data(item)
        assert "target_mapping" not in public
        assert "target_sequence" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_unresolved_food_forms_are_not_active() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=7)
        rendered = repr(public_game_data(item))
        for form in UNRESOLVED_SOURCE_FORMS:
            assert form not in rendered


def test_duplicate_food_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-FOOD-VOCAB-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["word_token"] = response["placements"][0]["word_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_FOOD_MAPPING"):
        validate_constructed_response(item, response)


def test_food_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("food_word_visual_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
    sparse = infer_belief("not-a-label", sparse=True)
    assert sparse["predicted_label"] == "unknown_or_other"
    assert sparse["fallback_used"] is True


def test_basket_sort_uses_concrete_foods_and_places_coconut_with_fruit() -> None:
    from app.gamification.content.island_food_festival import FOODS

    assert next(row[3] for row in FOODS if row[0] == "coconut") == "fruits"
    concrete = {row[1] for row in FOODS if row[4]}
    for seed in range(40):
        item = generate_item("G5-ENG-FOOD-GROUP-02", role="unsupported_before", seed=seed)
        assert all(row["text_en"] in concrete for row in item.game_data["entries"])
        assert len(item.game_data["entries"]) == len(item.game_data["stalls"]) == 5


def test_name_puzzles_require_a_distinct_food_visual() -> None:
    for seed in range(24):
        item = generate_item("G5-ENG-FOOD-NAME-03", role="unsupported_before", seed=seed)
        assert item.game_data["renderer_variant"] in {11, 15, 26, 27, 31}
