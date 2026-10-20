import pytest

from app.gamification.content.information_station import (
    BLOCKED_VISUAL_FORMS,
    MISCONCEPTIONS,
    SOURCE_PAIRS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_source_vocabulary_and_visual_meaning_gate():
    assert [(row[1], row[2]) for row in SOURCE_PAIRS] == [
        ("Letter", "ලියුම"),
        ("Newspapers", "පුවත්පත්"),
        ("Telephone", "දුරකථනය"),
        ("Post", "තැපෑල"),
    ]
    assert BLOCKED_VISUAL_FORMS == ("Letter", "Post")

    item = generate_item("G5-ENG-INFO-VISUAL-02", role="unsupported_before", seed=7)
    visible_words = {row["text_en"] for row in item.game_data["words"]}
    assert visible_words == {"Newspapers", "Telephone"}
    assert visible_words.isdisjoint(BLOCKED_VISUAL_FORMS)


@pytest.mark.parametrize(
    "skill_id",
    ["G5-ENG-INFO-BILINGUAL-01", "G5-ENG-INFO-VISUAL-02"],
)
def test_public_manifest_strips_answers_and_server_scores(skill_id):
    item = generate_item(skill_id, role="unsupported_before", seed=3)
    public = public_game_data(item)

    assert "target_mapping" not in public
    assert validate_constructed_response(item, correct_response(item.game_data))[0]


def test_constructed_response_is_strict_and_sparse_belief_is_normalized():
    item = generate_item("G5-ENG-INFO-BILINGUAL-01", role="unsupported_before", seed=3)
    response = correct_response(item.game_data)
    response["unexpected"] = True
    with pytest.raises(ValueError, match="MALFORMED_INFORMATION_RESPONSE"):
        validate_constructed_response(item, response)

    belief = infer_belief("not-in-catalogue", sparse=True)
    assert belief["predicted_label"] == "unknown_or_other"
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1.0)
