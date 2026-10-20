import pytest

from app.gamification.content.conversation_street import (
    ACTIVE_PAIRS,
    BLOCKED_SOURCE_ANSWERS,
    MISCONCEPTIONS,
    PET_STATEMENTS,
    SOURCE_PAIRS,
    STANDALONE_STATEMENTS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_exact_source_evidence_counts_and_adjacency_are_preserved():
    assert len(SOURCE_PAIRS) == 27
    assert len(STANDALONE_STATEMENTS) == 9
    assert len(PET_STATEMENTS) == 10
    assert SOURCE_PAIRS[0][:2] == ("What's your name?", "I am Ruwan.")
    assert SOURCE_PAIRS[-1][:2] == ("What is in my hand?", "An umbrella.")


def test_unresolved_source_forms_fail_closed_from_active_items():
    assert "I have two sister." in BLOCKED_SOURCE_ANSWERS
    assert "No, I don't have." in BLOCKED_SOURCE_ANSWERS
    assert "Sorry, I don't have." in BLOCKED_SOURCE_ANSWERS
    assert not BLOCKED_SOURCE_ANSWERS.intersection(answer for _, answer in ACTIVE_PAIRS)
    for skill_id in (
        "G5-ENG-CONV-PAIR-01",
        "G5-ENG-CONV-TURN-02",
        "G5-ENG-CONV-FRAME-03",
        "G5-ENG-CONV-DESCRIBE-04",
    ):
        for seed in range(8):
            item = generate_item(skill_id, role="unsupported_before", seed=seed)
            assert not any(blocked in str(item.game_data) for blocked in BLOCKED_SOURCE_ANSWERS)


@pytest.mark.parametrize(
    "skill_id",
    [
        "G5-ENG-CONV-PAIR-01",
        "G5-ENG-CONV-TURN-02",
        "G5-ENG-CONV-FRAME-03",
        "G5-ENG-CONV-DESCRIBE-04",
    ],
)
def test_public_manifest_strips_answers_and_uses_fictional_policy(skill_id):
    item = generate_item(skill_id, role="unsupported_before", seed=18)
    public = public_game_data(item)
    assert not (
        {"target_mapping", "target_sequence", "target_speakers", "target_response", "bound_fact"}
        & public.keys()
    )
    assert public["profile_policy_version"] == "fictional-profile-only-v1"
    assert "yourself" in public["fictional_notice"]
    assert validate_constructed_response(item, correct_response(item.game_data))[0]


def test_profile_manifest_contains_only_server_owned_fictional_facts():
    item = generate_item("G5-ENG-CONV-FRAME-03", role="unsupported_before", seed=18)
    public = public_game_data(item)
    assert str(public["profile_label"]).startswith("Fictional profile")
    assert {row["label"] for row in public["profile_facts"]} == {"Name", "Age", "Ability"}
    assert not ({"input", "free_text", "learner_name", "address", "location"} & public.keys())


def test_pair_manifest_always_contains_two_distinct_questions():
    for seed in range(100):
        item = generate_item("G5-ENG-CONV-PAIR-01", role="unsupported_before", seed=seed)
        questions = item.game_data["questions"]
        mapping = item.game_data["target_mapping"]
        assert isinstance(questions, list)
        assert isinstance(mapping, dict)
        assert len(questions) == len(mapping) == 2


def test_strict_schema_rejects_free_text_and_personal_fields():
    item = generate_item("G5-ENG-CONV-PAIR-01", role="unsupported_before", seed=18)
    for field in ("free_text", "learner_name", "age", "school", "location", "voice"):
        malformed = correct_response(item.game_data)
        malformed[field] = "private"
        with pytest.raises(ValueError, match="MALFORMED_CONVERSATION_STREET_RESPONSE"):
            validate_constructed_response(item, malformed)


def test_sparse_belief_is_finite_and_normalized():
    belief = infer_belief("unregistered", sparse=True)
    assert belief["predicted_label"] == "unknown_or_other"
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1.0)
