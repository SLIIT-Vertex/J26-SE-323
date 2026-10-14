"""No API schema may ever carry the answer key or the grader's instruction text."""

from typing import Any

from app.main import app

FORBIDDEN = {"correct_option", "accepted_answers", "instruction", "answer_key_raw"}


def property_names(node: Any) -> set[str]:
    """Every object key and every schema property name found anywhere in the document."""
    names: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            names.add(key)
            names |= property_names(value)
    elif isinstance(node, list):
        for item in node:
            names |= property_names(item)
    return names


def test_no_endpoint_exposes_the_answer_key() -> None:
    leaked = property_names(app.openapi()) & FORBIDDEN

    assert not leaked, f"answer-key fields exposed by the API: {sorted(leaked)}"


def test_the_check_would_catch_a_leak() -> None:
    schema = {
        "components": {
            "schemas": {"Question": {"properties": {"id": {}, "correct_option": {"type": "string"}}}}
        }
    }

    assert property_names(schema) & FORBIDDEN == {"correct_option"}
