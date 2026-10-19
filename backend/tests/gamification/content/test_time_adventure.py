import pytest

from app.gamification.content.time_adventure import (
    ATOMIC_SKILLS,
    generate_item,
    validate_constructed_response,
)


def response_for(item):
    game = item.game_data
    kind = game["response_kind"]
    if kind == "time_unit_match":
        return {"kind": kind, "matches": list(game["correct_matches"])}
    if kind == "analog_clock":
        return {"kind": kind, "hour": game["target_hour"], "minute": game["target_minute"]}
    if kind == "time_conversion":
        hour = int(game["source_hour"])
        hour24 = (0 if hour == 12 else hour) if game["period"] == "am" else (12 if hour == 12 else hour + 12)
        return {"kind": kind, "hour24": hour24, "minute": game["source_minute"]}
    if kind == "elapsed_time":
        minutes = (game["end_hour"] * 60 + game["end_minute"]) - (game["start_hour"] * 60 + game["start_minute"])
        return {"kind": kind, "hours": minutes // 60, "minutes": minutes % 60}
    if game["operation"] == "add":
        total = (game["left_hours"] + game["right_hours"]) * 60 + game["left_minutes"] + game["right_minutes"]
    else:
        total = game["left_hours"] * 60 + game["left_minutes"] - (game["right_hours"] * 60 + game["right_minutes"])
    return {"kind": kind, "hours": total // 60, "minutes": total % 60, "regrouped": True}


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda skill: skill.skill_id)
def test_time_items_are_server_scored(skill):
    item = generate_item(skill.skill_id, role="unsupported_before", seed=721)
    correct, error, normalized = validate_constructed_response(item, response_for(item))
    assert correct is True
    assert error == "correct"
    assert normalized["kind"] == skill.response_kind


def test_midnight_and_regrouping_are_base_sixty():
    item = generate_item("G5-MAT-TIME-24H-01", role="unsupported_before", seed=8)
    item.game_data.update(source_hour=12, source_minute=0, period="am")
    assert validate_constructed_response(item, {"kind": "time_conversion", "hour24": 0, "minute": 0})[0]
    arithmetic = generate_item("G5-MAT-TIME-ARITHMETIC-01", role="unsupported_before", seed=4)
    arithmetic.game_data.update(operation="add", left_hours=3, left_minutes=45, right_hours=2, right_minutes=35)
    assert validate_constructed_response(arithmetic, {"kind": "time_arithmetic", "hours": 6, "minutes": 20, "regrouped": True})[0]
