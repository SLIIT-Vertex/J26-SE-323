import copy
import json
import re
from typing import Any

from app.curriculum.infrastructure import JsonlCurriculumSourceRegistry
from app.gamification.content import PILOT_CONTENT_DIRECTORY
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY

from .pilot_builder import BUILDER

SYNTHETIC_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "synthetic-model-data" / "v1"
SYNTHETIC_LABEL_KEYS = ("expert_misconception_label", "alternative_plausible_label", "label")


def authored() -> dict[str, list[dict[str, Any]]]:
    return BUILDER.load_authored(PILOT_CONTENT_DIRECTORY)


def test_committed_package_is_reproducible_and_rebuilds_identically() -> None:
    context = BUILDER.load_context()
    first = BUILDER.build_outputs(PILOT_CONTENT_DIRECTORY, context)
    second = BUILDER.build_outputs(PILOT_CONTENT_DIRECTORY, context)

    assert first == second
    for name, text in first.items():
        assert (PILOT_CONTENT_DIRECTORY / name).read_text(encoding="utf-8") == text, name


def test_every_cited_source_resolves_in_the_shared_registry() -> None:
    registry = JsonlCurriculumSourceRegistry()
    rows = authored()
    cited = {row["source_id"] for row in rows["source_documents.jsonl"]}
    cited |= {
        citation["source_id"]
        for row in rows["skills.jsonl"]
        for citation in row["source_citations"]
    }
    cited |= {row["source_reference"]["source_id"] for row in rows["items.jsonl"]}
    cited |= {row["source_reference"]["source_id"] for row in rows["content_assets.jsonl"]}

    assert cited == {"SRC-G5-MAT-TB-01", "SRC-G5-MAT-TG-01", "SRC-G5-MAT-TG-02"}
    for source_id in cited:
        assert registry.get_source(source_id) is not None, source_id


def test_source_documents_pin_a_sha256_per_pdf() -> None:
    documents = authored()["source_documents.jsonl"]
    manifest = json.loads((PILOT_CONTENT_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))

    assert len(documents) == 3
    for row in documents:
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        assert manifest["source_documents"][row["source_id"]]["sha256"] == row["sha256"]


def test_readiness_gates_wait_only_for_educator_review() -> None:
    report = json.loads(
        (PILOT_CONTENT_DIRECTORY / "readiness_report.json").read_text(encoding="utf-8")
    )
    gates = {name: gate["status"] for name, gate in report["gates"].items()}

    assert gates == {
        "misconception_inference": "ready_pending_review",
        "support_selection": "ready_pending_review",
        "independence_gain": "ready_pending_review",
        "child_facing_delivery": "blocked_pending_review",
    }
    assert report["review"]["approved_records"] == 0


def _errors_after(mutate: Any) -> list[str]:
    rows = copy.deepcopy(authored())
    mutate(rows)
    return BUILDER.validate(rows, BUILDER.load_context())


def _first_choice_item(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return next(row for row in rows["items.jsonl"] if row["response_format"] == "single_choice")


def test_validation_passes_for_the_authored_package() -> None:
    assert BUILDER.validate(authored(), BUILDER.load_context()) == []


def test_validation_rejects_an_unmapped_wrong_option() -> None:
    def mutate(rows: dict[str, list[dict[str, Any]]]) -> None:
        item = _first_choice_item(rows)
        wrong = next(
            o for o in item["answer_options"] if o["option_id"] != item["correct_option_id"]
        )
        wrong["misconception_code"] = None

    assert any("has no misconception" in error for error in _errors_after(mutate))


def test_validation_rejects_a_worked_example_that_shares_item_values() -> None:
    def mutate(rows: dict[str, list[dict[str, Any]]]) -> None:
        asset = next(
            row for row in rows["content_assets.jsonl"] if row["scaffold_type"] == "worked_example"
        )
        item = next(row for row in rows["items.jsonl"] if row["skill_id"] == asset["skill_id"])
        asset["parameters"] = dict(item["parameters"])

    assert any("shares values" in error for error in _errors_after(mutate))


def test_validation_rejects_a_template_outside_the_compatibility_table() -> None:
    def mutate(rows: dict[str, list[dict[str, Any]]]) -> None:
        item = _first_choice_item(rows)
        item["compatible_templates"] = [*item["compatible_templates"], "sort_and_group"]

    assert any("exceed the table entry" in error for error in _errors_after(mutate))


def test_validation_rejects_a_skill_without_all_three_scaffold_arms() -> None:
    def mutate(rows: dict[str, list[dict[str, Any]]]) -> None:
        rows["scaffolds.jsonl"] = [
            row for row in rows["scaffolds.jsonl"] if row["scaffold_type"] != "visual_guidance"
        ]

    assert any("missing scaffold arms" in error for error in _errors_after(mutate))


def test_validation_rejects_a_citation_outside_its_curriculum_node() -> None:
    def mutate(rows: dict[str, list[dict[str, Any]]]) -> None:
        citation = rows["skills.jsonl"][0]["source_citations"][0]
        citation["page_from"] = citation["page_to"] = "150"

    assert any(
        "is not inside one of its curriculum nodes" in error for error in _errors_after(mutate)
    )


def _synthetic_labels(value: Any) -> set[str]:
    labels: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "expert_review_template":
                continue
            if key in SYNTHETIC_LABEL_KEYS and isinstance(child, str):
                labels.add(child)
            labels |= _synthetic_labels(child)
    elif isinstance(value, list):
        for child in value:
            labels |= _synthetic_labels(child)
    return labels


def test_synthetic_fixture_labels_resolve_to_the_synthetic_catalogue() -> None:
    catalogue = json.loads(
        (SYNTHETIC_DIRECTORY / "synthetic-misconception-catalogue.json").read_text(encoding="utf-8")
    )
    known = set(catalogue["misconception_codes"]) | set(catalogue["reserved_codes"])
    pilot_codes = {row["misconception_code"] for row in authored()["misconception_catalogue.jsonl"]}

    assert catalogue["synthetic"] is True
    assert catalogue["catalogue_version"] == "synthetic-misconceptions-v1"
    for name in catalogue["applies_to"]:
        data = json.loads((SYNTHETIC_DIRECTORY / name).read_text(encoding="utf-8"))
        assert _synthetic_labels(data) <= known, name
    assert set(catalogue["reserved_codes"]) <= pilot_codes
    assert not set(catalogue["misconception_codes"]) & pilot_codes
    assert not set(catalogue["structured_error_codes"]) & pilot_codes
