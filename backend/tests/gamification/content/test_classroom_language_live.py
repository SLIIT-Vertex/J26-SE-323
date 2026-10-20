import pytest

from app.gamification.content.classroom_language_live import (
    MISCONCEPTIONS,
    SOURCE_GROUPS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_exact_source_groups_and_counts_are_preserved():
    assert {heading: len(forms) for heading, forms in SOURCE_GROUPS.items()} == {
        "Greetings and Wishes": 10,
        "Simple Commands": 11,
        "Request": 7,
        "Praising": 5,
        "Polite Forms": 3,
        "Simple Question Forms": 7,
    }
    assert "Don't go out" in SOURCE_GROUPS["Simple Commands"]
    assert "I'm sorry" in SOURCE_GROUPS["Polite Forms"]
    assert "Is it a ................. ?" in SOURCE_GROUPS["Simple Question Forms"]


@pytest.mark.parametrize(
    "skill_id",
    [
        "G5-ENG-CLASS-FUNCTION-01",
        "G5-ENG-CLASS-COMMAND-02",
        "G5-ENG-CLASS-CONTEXT-03",
        "G5-ENG-CLASS-QUESTION-04",
    ],
)
def test_public_manifest_hides_answers_and_server_scores(skill_id):
    item = generate_item(skill_id, role="unsupported_before", seed=17)
    public = public_game_data(item)
    assert not (
        {"target_mapping", "target_action", "target_state", "target_sequence"} & public.keys()
    )
    assert validate_constructed_response(item, correct_response(item.game_data))[0]


def test_command_activity_is_fictional_and_uses_opaque_scene_state():
    item = generate_item("G5-ENG-CLASS-COMMAND-02", role="unsupported_before", seed=17)
    public = public_game_data(item)
    assert public["actor_token"].startswith("a-")
    assert all(control["state_token"].startswith("s-") for control in public["action_controls"])
    assert "target_action" not in public and "target_state" not in public
    assert not ({"camera", "microphone", "motion", "gaze"} & public.keys())


def test_strict_schema_and_sparse_normalized_belief():
    item = generate_item("G5-ENG-CLASS-QUESTION-04", role="unsupported_before", seed=17)
    malformed = correct_response(item.game_data)
    malformed["unexpected"] = True
    with pytest.raises(ValueError, match="MALFORMED_CLASSROOM_LANGUAGE_RESPONSE"):
        validate_constructed_response(item, malformed)
    belief = infer_belief("unregistered", sparse=True)
    assert belief["predicted_label"] == "unknown_or_other"
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1.0)
