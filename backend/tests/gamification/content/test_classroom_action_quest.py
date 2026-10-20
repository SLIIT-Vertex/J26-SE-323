from app.gamification.content.classroom_action_quest import (
    BODY_COMMANDS,
    SKILLS,
    correct_response,
    generate_item,
    infer_belief,
    public_game_data,
    validate_constructed_response,
)


def test_each_skill_has_answer_free_public_item_and_valid_constructed_response() -> None:
    for skill_id in SKILLS:
        item = generate_item(skill_id, role="unsupported_before", seed=31)
        public = public_game_data(item)
        assert "command_id" not in public
        assert public["command_token"] != item.game_data["command_id"]
        assert "target_body_state" not in public
        assert "target_location_id" not in public
        response = correct_response(item.game_data)
        assert validate_constructed_response(item, response)[:2] == (True, "correct")


def test_body_command_family_is_complete() -> None:
    assert {row[0] for row in BODY_COMMANDS} == {
        "bend",
        "stretch_arms",
        "arms_down",
        "stand_straight",
        "turn_around",
        "sit_down",
    }


def test_wrong_landmark_is_structured_misconception_evidence() -> None:
    item = generate_item("G5-ENG-BEH-DESTINATION-01", role="unsupported_before", seed=4)
    response = correct_response(item.game_data)
    response["final_location_id"] = (
        "wall-zone" if response["final_location_id"] == "blackboard-zone" else "blackboard-zone"
    )
    response["movement_path"] = [
        {"sequence": 1, "action": "move", "destination_id": response["final_location_id"]}
    ]
    correct, error, _ = validate_constructed_response(item, response)
    assert correct is False
    assert error == "wall_vs_blackboard_noun_confusion"


def test_belief_is_normalized_and_retains_unknown() -> None:
    belief = infer_belief("bend_vs_sit_confusion")
    probabilities = belief["probabilities"]
    assert "unknown_or_other" in probabilities
    assert abs(sum(probabilities.values()) - 1.0) < 1e-9
