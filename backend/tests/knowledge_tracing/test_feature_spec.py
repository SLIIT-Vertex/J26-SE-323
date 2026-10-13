"""The shared feature spec is the single source of truth for training and serving."""

import json
from pathlib import Path

import pytest

from app.knowledge_tracing.application.question_files import parse_skill_nodes

ROOT = Path(__file__).parents[3]
SPEC = ROOT / "shared" / "feature_spec.json"
NODES = ROOT / "backend" / "data" / "question_bank" / "skill_nodes.md"


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_thirty_unique_skills(spec: dict) -> None:
    skills = spec["skills"]

    assert len(skills) == 30
    assert len(set(skills)) == 30


def test_coding_matches_the_documented_rules(spec: dict) -> None:
    assert spec["source_coding"] == {"digital": 1, "paper": 0}
    assert spec["difficulty_to_model_value"] == {"easy": 0.0, "medium": 0.5, "hard": 1.0}
    assert spec["penalty"]["paper_default"] == 0.08
    assert spec["history_cap_steps"] == 140
    assert spec["min_attempts_for_known_skill"] == 3


@pytest.mark.skipif(not NODES.is_file(), reason="skill_nodes.md not present")
def test_spec_order_equals_skill_nodes_order(spec: dict) -> None:
    nodes, issues = parse_skill_nodes(NODES.read_text(encoding="utf-8"))

    assert issues == []
    assert [n.code for n in nodes] == spec["skills"]
