import copy
import json
import unicodedata
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.gamification.content.curriculum_registry import (
    CURRICULUM_CONTENT_DIRECTORY,
    PublicCurriculumPackage,
    load_curriculum_public_package,
    load_curriculum_server_answer_keys,
)


def raw_public() -> dict[str, object]:
    return json.loads((CURRICULUM_CONTENT_DIRECTORY / "public_content.json").read_text(encoding="utf-8"))


def validate_after(change: object) -> PublicCurriculumPackage:
    data = copy.deepcopy(raw_public())
    change(data)
    return PublicCurriculumPackage.model_validate(data)


def test_package_is_one_atomic_draft_and_child_delivery_fails_closed() -> None:
    package = load_curriculum_public_package(allow_draft=True)

    assert package.scope == "one_atomic_grade5_sinhala_skill"
    assert package.skill.skill_id == "G5-MAT-C03-L01-O01"
    assert package.source.official_outcome_code is None
    assert package.source.printed_page == 31
    assert package.approved_for_child_delivery() is False
    with pytest.raises(PermissionError, match="blocked"):
        load_curriculum_public_package()


@pytest.mark.parametrize(
    ("field", "value"),
    [("grade", 4), ("medium", "ta")],
)
def test_grade4_and_tamil_medium_are_rejected(field: str, value: object) -> None:
    def mutate(data: dict[str, object]) -> None:
        source = data["source"]
        assert isinstance(source, dict)
        source[field] = value

    with pytest.raises(ValidationError):
        validate_after(mutate)


@pytest.mark.parametrize(
    "field", ["source_id", "title", "edition", "printed_page", "exact_outcome_si"]
)
def test_source_title_edition_page_and_exact_outcome_are_required(field: str) -> None:
    def mutate(data: dict[str, object]) -> None:
        source = data["source"]
        assert isinstance(source, dict)
        source.pop(field)

    with pytest.raises(ValidationError):
        validate_after(mutate)


def test_approval_without_a_reviewer_is_rejected() -> None:
    def mutate(data: dict[str, object]) -> None:
        reviews = data["reviews"]
        assert isinstance(reviews, list)
        reviews[0]["status"] = "approved"

    with pytest.raises(ValidationError, match="reviewer_id"):
        validate_after(mutate)


def test_content_approval_without_a_reviewer_is_rejected() -> None:
    def mutate(data: dict[str, object]) -> None:
        items = data["item_revisions"]
        assert isinstance(items, list)
        items[0]["review_status"] = "approved"

    with pytest.raises(ValidationError, match="reviewer identity"):
        validate_after(mutate)


def test_rubric_approval_without_a_reviewer_is_rejected() -> None:
    def mutate(data: dict[str, object]) -> None:
        items = data["item_revisions"]
        assert isinstance(items, list)
        items[0]["rubric_review_status"] = "approved"

    with pytest.raises(ValidationError, match="reviewer identity"):
        validate_after(mutate)


def test_human_verified_source_requires_verifier_identity_and_date() -> None:
    def mutate(data: dict[str, object]) -> None:
        source = data["source"]
        assert isinstance(source, dict)
        source["verification_status"] = "human_verified"

    with pytest.raises(ValidationError, match="verifier identity"):
        validate_after(mutate)


def test_all_child_facing_sinhala_is_unicode_nfc() -> None:
    package = load_curriculum_public_package(allow_draft=True)
    values = [package.skill.name_si, package.source.exact_outcome_si]
    values.extend(item.prompt_si for item in package.item_revisions)
    values.extend(scaffold.title_si for scaffold in package.scaffolds)
    values.extend(step for scaffold in package.scaffolds for step in scaffold.body_si)
    values.extend(row.label_si for row in package.misconceptions)

    for value in values:
        contains_sinhala = any("\u0D80" <= character <= "\u0DFF" for character in value)
        assert contains_sinhala or value == "20 ÷ 2 = 10"
        assert unicodedata.is_normalized("NFC", value)
        assert "\ufffd" not in value


def test_item_revisions_and_skill_records_are_immutable_and_stably_versioned() -> None:
    package = load_curriculum_public_package(allow_draft=True)
    assert len({item.item_id for item in package.item_revisions}) == 3
    assert len({item.revision_id for item in package.item_revisions}) == 3
    assert all("@v1" in item.revision_id for item in package.item_revisions)
    with pytest.raises((ValidationError, FrozenInstanceError)):
        package.item_revisions[0].total = 99  # type: ignore[misc]
    with pytest.raises(ValidationError):
        validate_after(
            lambda data: data["skill"].__setitem__("skill_id", "draft-half")  # type: ignore[union-attr]
        )


def test_public_package_contains_no_answer_keys_or_rubrics() -> None:
    raw = (CURRICULUM_CONTENT_DIRECTORY / "public_content.json").read_text(encoding="utf-8")
    assert "correct_option_id" not in raw
    assert '"rubric"' not in raw
    package = load_curriculum_public_package(allow_draft=True)
    public_fields = set(type(package.item_revisions[0]).model_fields)
    assert {"correct_option_id", "accepted_response", "rubric", "scoring_version"}.isdisjoint(
        public_fields
    )

    keys = load_curriculum_server_answer_keys()
    assert set(keys) == {item.revision_id for item in package.item_revisions}


def test_scaffold_probe_value_reuse_is_rejected_as_answer_leakage() -> None:
    def mutate(data: dict[str, object]) -> None:
        scaffolds = data["scaffolds"]
        assert isinstance(scaffolds, list)
        scaffolds[0]["worked_values"] = [8]

    with pytest.raises(ValidationError, match="reuses a probe value"):
        validate_after(mutate)


def test_parallel_family_has_equivalent_but_distinct_probes() -> None:
    package = load_curriculum_public_package(allow_draft=True)
    family = package.parallel_family
    assert family.revision_ids == tuple(item.revision_id for item in package.item_revisions)
    assert len({(item.object_kind, item.total) for item in package.item_revisions}) == 3
    keys = load_curriculum_server_answer_keys()
    assert len({key.accepted_response for key in keys.values()}) == 3
    assert {item.measurement_role for item in package.item_revisions} == {
        "unsupported_before",
        "supported_practice",
        "unsupported_after",
    }
    assert all(
        item.assistance_allowed == (item.measurement_role == "supported_practice")
        for item in package.item_revisions
    )


def test_probe_revision_reuse_is_rejected() -> None:
    def mutate(data: dict[str, object]) -> None:
        items = data["item_revisions"]
        family = data["parallel_family"]
        assert isinstance(items, list) and isinstance(family, dict)
        items[2]["revision_id"] = items[0]["revision_id"]
        family["revision_ids"][2] = family["revision_ids"][0]

    with pytest.raises(ValidationError, match="distinct"):
        validate_after(mutate)


def test_required_review_domains_and_unknown_fallback_are_present() -> None:
    package = load_curriculum_public_package(allow_draft=True)
    assert {review.review_kind for review in package.reviews} == {
        "curriculum",
        "sinhala_language",
        "accessibility",
        "answer_leakage",
    }
    assert "unknown_or_other" in {row.misconception_id for row in package.misconceptions}
    assert all(review.status == "pending" for review in package.reviews)


def test_manifest_hashes_reject_unreviewed_file_mutation(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    for source in CURRICULUM_CONTENT_DIRECTORY.iterdir():
        (package_dir / source.name).write_bytes(source.read_bytes())
    content = package_dir / "public_content.json"
    content.write_text(
        content.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n"
    )

    with pytest.raises(ValueError, match="immutable manifest"):
        load_curriculum_public_package(package_dir, allow_draft=True)
