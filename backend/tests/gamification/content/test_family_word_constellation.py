import pytest

from app.gamification.content.family_word_constellation import (
    BLOCKED_FORM_SKILL,
    BLOCKED_SOURCE_FORMS,
    MISCONCEPTIONS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_blocked_grand_forms_are_absent_and_form_skill_is_closed() -> None:
    with pytest.raises(ValueError, match="FAMILY_FORM_REVIEW_BLOCKED"):
        generate_item(BLOCKED_FORM_SKILL, role="unsupported_before", seed=1)
    for seed in (0, 1, 2):
        item = generate_item("G5-ENG-FAMILY-BILINGUAL-01", role="unsupported_before", seed=seed)
        public = public_game_data(item)
        rendered = repr(public)
        assert "target_mapping" not in public
        assert public["sinhala_pairing_status"] == "unverified_candidate"
        for form in BLOCKED_SOURCE_FORMS:
            assert form not in rendered
        assert validate_constructed_response(item, correct_response(item.game_data))[:2] == (True, "correct")


def test_duplicate_family_link_is_rejected() -> None:
    item = generate_item("G5-ENG-FAMILY-BILINGUAL-01", role="unsupported_before", seed=1)
    response = correct_response(item.game_data)
    response["links"][1]["sinhala_token"] = response["links"][0]["sinhala_token"]
    with pytest.raises(ValueError, match="INCOMPLETE_OR_DUPLICATE_FAMILY_LINKS"):
        validate_constructed_response(item, response)


def test_family_belief_normalizes_with_unknown() -> None:
    belief = infer_belief("father_mother_confusion")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert abs(sum(belief["probabilities"].values()) - 1.0) < 1e-9
    sparse = infer_belief("not-a-label", sparse=True)
    assert sparse["predicted_label"] == "unknown_or_other"
