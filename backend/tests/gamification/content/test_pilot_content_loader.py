import json
import unicodedata
from pathlib import Path

import pytest

from app.gamification.content import (
    CANONICAL_SCAFFOLD_ARMS,
    PILOT_CONTENT_DIRECTORY,
    ContentStatus,
    ResponseFormat,
    load_pilot_content_package,
    skill_support_candidates,
)
from app.gamification.domain.types import SupportActionType
from app.gamification.skill_catalogue import ReviewStatus

from .pilot_builder import STATUS_FIELDS, copy_package, read_jsonl, rebuild, write_jsonl

SINHALA_BLOCK = range(0x0D80, 0x0E00)


def test_loader_fails_closed_on_draft_records() -> None:
    with pytest.raises(PermissionError, match="not approved"):
        load_pilot_content_package()


def test_allow_draft_exposes_typed_records() -> None:
    package = load_pilot_content_package(allow_draft=True)

    assert len(package.skills) == 5
    assert {skill.universal_skill_id for skill in package.skills.values()} == {"MAT-FRC"}
    assert all(skill.review.status is ReviewStatus.DRAFT for skill in package.skills.values())
    assert all(item.status is ContentStatus.DRAFT for item in package.items.values())
    assert package.versions["catalogue_version"] == "grade5-pilot-misconceptions-v1"
    for skill_id in package.skills:
        groups = package.groups_for_skill(skill_id)
        assert len(groups) >= 2
        assert all(len(group.item_ids) >= 3 for group in groups)


def test_every_wrong_choice_resolves_to_a_catalogue_misconception() -> None:
    package = load_pilot_content_package(allow_draft=True)

    for item in package.items.values():
        for option in item.answer_options:
            if item.response_format is not ResponseFormat.BINARY_SORT and (
                option.option_id == item.correct_option_id
            ):
                continue
            code = package.misconception_for(item.item_id, option.option_id)
            assert code in package.misconceptions


def test_support_candidates_cover_three_arms_per_skill_in_sinhala() -> None:
    package = load_pilot_content_package(allow_draft=True)

    for skill_id in package.skills:
        candidates = skill_support_candidates(package, skill_id)
        assert len(candidates) >= 3
        assert [candidate.action_type for candidate in candidates] == [
            SupportActionType.VISUAL_GUIDANCE,
            SupportActionType.SIMILAR_WORKED_EXAMPLE,
            SupportActionType.GUIDED_STEPS,
        ]
        assert all(candidate.languages == ("si",) for candidate in candidates)
        assert all(skill_id in candidate.skill_ids for candidate in candidates)
        assert not any(candidate.approved for candidate in candidates)
        scaffolds = package.scaffolds_for_skill(skill_id)
        assert {scaffold.scaffold_type for scaffold in scaffolds} >= set(CANONICAL_SCAFFOLD_ARMS)


def test_sinhala_text_round_trips_through_the_loader() -> None:
    package = load_pilot_content_package(allow_draft=True)
    raw_items = {row["item_id"]: row for row in read_jsonl(PILOT_CONTENT_DIRECTORY / "items.jsonl")}
    raw_assets = {
        row["content_asset_id"]: row
        for row in read_jsonl(PILOT_CONTENT_DIRECTORY / "content_assets.jsonl")
    }

    for item_id, item in package.items.items():
        assert item.question_text == raw_items[item_id]["question_text"]
        assert any(ord(character) in SINHALA_BLOCK for character in item.question_text)
        assert unicodedata.is_normalized("NFC", item.question_text)
        assert [option.text for option in item.answer_options] == [
            option["text"] for option in raw_items[item_id]["answer_options"]
        ]
    for asset_id, asset in package.content_assets.items():
        assert list(asset.body_si) == raw_assets[asset_id]["body_si"]
        assert asset.title_si == raw_assets[asset_id]["title_si"]
    for misconception in package.misconceptions.values():
        assert any(ord(character) in SINHALA_BLOCK for character in misconception.label_si)


def test_loader_rejects_files_that_do_not_match_the_manifest(tmp_path: Path) -> None:
    package_dir = copy_package(tmp_path)
    items = package_dir / "items.jsonl"
    items.write_text(
        items.read_text(encoding="utf-8").replace("G5-MAT-FRC-I001", "G5-MAT-FRC-I999", 1),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="items.jsonl does not match"):
        load_pilot_content_package(package_dir, allow_draft=True)


def test_reviewer_approval_unlocks_the_package_without_rewriting_content(tmp_path: Path) -> None:
    package_dir = copy_package(tmp_path)
    for name, field in STATUS_FIELDS.items():
        rows = read_jsonl(package_dir / name)
        for row in rows:
            row[field] = "approved"
            row["reviewer_id"] = "test-educator-reviewer"
            row["reviewed_on"] = "2026-10-14"
        write_jsonl(package_dir / name, rows)
    rebuild(package_dir)

    package = load_pilot_content_package(package_dir)

    assert all(item.status is ContentStatus.APPROVED for item in package.items.values())
    assert all(
        candidate.approved
        for skill_id in package.skills
        for candidate in skill_support_candidates(package, skill_id)
    )
    report = json.loads((package_dir / "readiness_report.json").read_text(encoding="utf-8"))
    assert report["gates"]["child_facing_delivery"]["status"] == "ready"


def test_approval_without_a_reviewer_is_rejected(tmp_path: Path) -> None:
    package_dir = copy_package(tmp_path)
    rows = read_jsonl(package_dir / "scaffolds.jsonl")
    rows[0]["approval_status"] = "approved"
    write_jsonl(package_dir / "scaffolds.jsonl", rows)

    with pytest.raises(ValueError, match="not draft but has no reviewer"):
        rebuild(package_dir)
