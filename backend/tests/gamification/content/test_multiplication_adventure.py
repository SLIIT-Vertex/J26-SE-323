from app.gamification.content.multiplication_adventure import (
    ATOMIC_SKILLS,
    generate_item,
    validate_constructed_response,
)


def test_five_activities_cover_the_textbook_ranges():
    assert [skill.skill_id for skill in ATOMIC_SKILLS] == [
        "G5-MAT-MUL-TABLE-01",
        "G5-MAT-MUL-BY-2-3-01",
        "G5-MAT-MUL-BY-4-6-01",
        "G5-MAT-MUL-BY-7-10-01",
        "G5-MAT-MUL-STORY-01",
    ]
    chapters = [skill.chapter for skill in ATOMIC_SKILLS]
    assert chapters.count("table_explorer") == 1
    assert chapters.count("column_workshop") == 3
    assert chapters.count("story_mission") == 1


def test_written_products_keep_left_to_right_digits_and_times_ten_shift():
    by_three = generate_item("G5-MAT-MUL-BY-2-3-01", role="unsupported_before", seed=3)
    by_ten = generate_item("G5-MAT-MUL-BY-7-10-01", role="unsupported_before", seed=0)
    assert by_three.game_data["multiplier"] in {2, 3}
    assert by_three.game_data["result_digits"][0] != 0
    assert int("".join(str(digit) for digit in by_three.game_data["result_digits"])) == by_three.game_data["product"]
    found_shift = False
    for seed in range(12):
        item = generate_item("G5-MAT-MUL-BY-7-10-01", role="unsupported_before", seed=seed)
        assert item.game_data["multiplier"] in {7, 8, 9, 10}
        if item.game_data["multiplier"] == 10:
            found_shift = True
            assert item.game_data["place_shift"] is True
            assert item.game_data["product"] == item.game_data["multiplicand"] * 10
            assert len(item.game_data["result_digits"]) == 4
    assert found_shift
    assert by_ten.game_data["multiplicand"] >= 100


def test_rejects_wrong_kind_and_scores_the_constructed_product():
    item = generate_item("G5-MAT-MUL-TABLE-01", role="unsupported_before", seed=4)
    wrong_kind, error, _normalized = validate_constructed_response(
        item, {"kind": "written_multiplication", "product": 1}
    )
    assert wrong_kind is False
    assert error == "unexpected_payload"
    correct, code, _normalized = validate_constructed_response(
        item,
        {
            "kind": "multiplication_fact",
            "multiplicand": item.game_data["multiplicand"],
            "multiplier": item.game_data["multiplier"],
            "product": item.game_data["product"],
        },
    )
    assert correct is True
    assert code == "ok"
    story = generate_item("G5-MAT-MUL-STORY-01", role="unsupported_before", seed=2)
    bad, story_error, _normalized = validate_constructed_response(
        story,
        {
            "kind": "multiplication_story",
            "group_size": story.game_data["group_size"],
            "group_count": story.game_data["group_count"],
            "product": story.game_data["product"] + 1,
        },
    )
    assert bad is False
    assert story_error == "uses_addition"
