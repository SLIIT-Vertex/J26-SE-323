import pytest

from app.gamification.content.heritage_museum_quest import (
    MISCONCEPTIONS,
    SOURCE_PAIRS,
    UNRESOLVED_RENDERERS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_exact_source_transcription_and_timber_form_preservation():
    assert [(row[1], row[2]) for row in SOURCE_PAIRS] == [
        ("Timber carvings", "ලී කැටයම්"),
        ("Stone carvings", "ගල් කැටයම්"),
        ("Palace", "මාලිගාව"),
        ("Throne", "සිංහාසනය"),
        ("Crown", "ඔටුන්න"),
    ]
    assert all(row[1] != "Wood carvings" for row in SOURCE_PAIRS)


def test_unresolved_renderer_terms_are_excluded_from_visual_items(monkeypatch):
    monkeypatch.setattr(
        "app.gamification.content.heritage_museum_quest.UNRESOLVED_RENDERERS",
        ("Crown",),
    )
    item = generate_item("G5-ENG-PAST-VISUAL-02", role="unsupported_before", seed=3)
    assert "Crown" not in {row["text_en"] for row in item.game_data["words"]}
    assert UNRESOLVED_RENDERERS == ()


@pytest.mark.parametrize(
    "skill_id",
    ["G5-ENG-PAST-BILINGUAL-01", "G5-ENG-PAST-VISUAL-02"],
)
def test_public_manifest_strips_answer_map_and_server_scores(skill_id):
    item = generate_item(skill_id, role="unsupported_before", seed=3)
    public = public_game_data(item)
    assert "target_mapping" not in public
    assert validate_constructed_response(item, correct_response(item.game_data))[0]


def test_strict_schema_and_sparse_normalized_belief():
    item = generate_item("G5-ENG-PAST-BILINGUAL-01", role="unsupported_before", seed=3)
    malformed = correct_response(item.game_data)
    malformed["unexpected"] = True
    with pytest.raises(ValueError, match="MALFORMED_HERITAGE_RESPONSE"):
        validate_constructed_response(item, malformed)
    belief = infer_belief("unregistered", sparse=True)
    assert belief["predicted_label"] == "unknown_or_other"
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1.0)
