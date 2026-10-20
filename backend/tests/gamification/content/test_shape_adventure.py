import pytest

from app.gamification.content.shape_adventure import (
    ATOMIC_SKILLS,
    PROPERTIES,
    correct_response,
    generate_item,
    validate_constructed_response,
)


def test_shape_package_has_exactly_three_textbook_activities():
    assert [skill.response_kind for skill in ATOMIC_SKILLS] == [
        "shape_property_table", "orientation_identification", "solid_net_match",
    ]
    assert PROPERTIES == {"cube": (6, 8, 12), "cuboid": (6, 8, 12), "cylinder": (2, 0, 2), "triangular_pyramid": (4, 4, 6)}


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_all_shape_responses_are_server_scored(skill):
    item = generate_item(skill.skill_id, role="unsupported_before", seed=13)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[0] is True


def test_shape_table_rejects_wrong_cylinder_vertex_count():
    item = generate_item("G5-MAT-SHAPE-TABLE-01", role="unsupported_before", seed=2)
    response = correct_response(item.game_data)
    cylinder = next(row for row in response["rows"] if row["solid_id"] == "cylinder")
    cylinder["vertices"] = 2
    correct, error, normalized = validate_constructed_response(item, response)
    assert correct is False
    assert error == "cylinder_has_vertices"
    assert normalized["_feedback_column"] == "cylinder:vertices"


def test_net_activity_contains_every_textbook_solid_and_parallel_probe_is_immutable():
    before = generate_item("G5-MAT-SOLID-NET-01", role="unsupported_before", seed=4)
    after = generate_item("G5-MAT-SOLID-NET-01", role="unsupported_after", seed=4)
    assert set(before.game_data["solid_ids"]) == {"cube", "cuboid", "cylinder", "triangular_pyramid"}
    assert before.revision_id != after.revision_id
    assert before.parallel_family_id == after.parallel_family_id
