import pytest

from app.gamification.content.plant_explorer import (
    MISCONCEPTIONS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_all_plant_skills_are_answer_free_and_score_server_side() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=31)
        public = public_game_data(item)
        assert "target_mapping" not in public
        assert "target_pairs" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_stem_and_trunk_never_share_one_probe() -> None:
    for seed in range(12):
        item = generate_item("G5-ENG-PLANT-PARTS-02", role="unsupported_before", seed=seed)
        words = {row["text_en"] for row in item.game_data["labels"]}
        assert not {"Stem", "Trunk"}.issubset(words)


def test_duplicate_mapping_is_rejected() -> None:
    item = generate_item("G5-ENG-PLANT-VOCAB-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][1]["word_token"] = response["placements"][0]["word_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_PLANT_MAPPING"):
        validate_constructed_response(item, response)


def test_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("singular_plural_number_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
