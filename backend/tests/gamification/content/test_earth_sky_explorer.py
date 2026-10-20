import pytest

from app.gamification.content.earth_sky_explorer import (
    BLOCKED_BILINGUAL_CONTRASTS,
    BLOCKED_FOR_ALL_SCORING,
    BLOCKED_VISUAL_FORMS,
    MISCONCEPTIONS,
    SOURCE_PAIRS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_exact_two_screen_source_forms_and_review_blocks() -> None:
    assert len(SOURCE_PAIRS) == 22
    assert [row[1] for row in SOURCE_PAIRS][11:15] == ["Rain drops", "Lightening", "Floods", "Thunder"]
    assert "Lightening" in BLOCKED_FOR_ALL_SCORING
    assert {"Hill", "Mountain", "Tank"} <= set(BLOCKED_BILINGUAL_CONTRASTS)
    assert {"Thunder", "Tank", "Hill", "Mountain"} <= set(BLOCKED_VISUAL_FORMS)


@pytest.mark.parametrize("skill_id", ["G5-ENG-EARTHSKY-BILINGUAL-01", "G5-ENG-EARTHSKY-VISUAL-02"])
def test_public_items_strip_answers_and_score_only_on_server(skill_id: str) -> None:
    item = generate_item(skill_id, role="unsupported_before", seed=3)
    public = public_game_data(item)
    assert "target_mapping" not in public
    assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")
    visible = str(public)
    assert "Lightening" not in visible and "Tank" not in visible
    if skill_id.endswith("VISUAL-02"):
        assert "Thunder" not in visible and "Hill" not in visible and "Mountain" not in visible


def test_unknown_cross_presentation_token_and_duplicate_target_are_rejected() -> None:
    item = generate_item("G5-ENG-EARTHSKY-VISUAL-02", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    response["placements"][0]["scene_token"] = "c-unknown"
    with pytest.raises(ValueError, match="INVALID_EARTH_SKY_TOKEN_OR_SEQUENCE"):
        validate_constructed_response(item, response)
    duplicate = correct_response(item.game_data)
    duplicate["placements"][1]["scene_token"] = duplicate["placements"][0]["scene_token"]
    with pytest.raises(ValueError, match="DUPLICATE_EARTH_SKY_SOURCE_OR_TARGET"):
        validate_constructed_response(item, duplicate)


def test_sparse_belief_is_normalized_and_falls_back_to_unknown() -> None:
    belief = infer_belief("unreviewed", sparse=True)
    assert belief["predicted_label"] == "unknown_or_other" and belief["fallback_used"] is True
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
