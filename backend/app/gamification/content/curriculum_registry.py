"""Fail-closed registry for the first Grade 5 Sinhala-medium curriculum slice.

The package is deliberately draft-only until real reviewers complete every required review.
Public item records never contain answer keys; scoring data is loaded through a server-only API.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY

CURRICULUM_CONTENT_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "grade5-sinhala-curriculum-slice" / "v1"
CURRICULUM_PACKAGE_VERSION = "grade5-sinhala-curriculum-v1"
SKILL_ID_PATTERN = re.compile(r"^G5-MAT-C\d{2}-L\d{2}-O\d{2}$")
REVISION_ID_PATTERN = re.compile(r"^[A-Z0-9-]+@v[1-9][0-9]*$")
SINHALA_PATTERN = re.compile(r"[\u0D80-\u0DFF]")
REQUIRED_REVIEW_KINDS = frozenset(
    {"curriculum", "sinhala_language", "accessibility", "answer_leakage"}
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewRecord(FrozenModel):
    review_kind: Literal["curriculum", "sinhala_language", "accessibility", "answer_leakage"]
    status: Literal["pending", "approved", "rejected"]
    reviewer_id: str | None
    reviewed_on: str | None
    notes: str

    @model_validator(mode="after")
    def require_real_approval_metadata(self) -> ReviewRecord:
        if self.status == "approved" and (not self.reviewer_id or not self.reviewed_on):
            raise ValueError("approved reviews require reviewer_id and reviewed_on")
        if self.status != "approved" and (self.reviewer_id or self.reviewed_on):
            raise ValueError("pending or rejected reviews cannot masquerade as approval")
        return self


class SourceRecord(FrozenModel):
    source_id: str
    title: str
    edition: str
    publisher_authority: str
    grade: Literal[5]
    medium: Literal["si"]
    subject: Literal["Mathematics"]
    printed_page: Annotated[int, Field(ge=1)]
    pdf_page: Annotated[int, Field(ge=1)]
    official_outcome_code: str | None
    internal_outcome_locator: str
    exact_outcome_si: str
    outcome_transcription_note: str
    source_path: str
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    authority_status: Literal["official"]
    authority_note: str
    usage_rights_status: Literal["unknown", "permitted", "restricted"]
    verification_status: Literal["source_located_pending_human_review", "human_verified"]
    verified_by: str | None
    verified_on: str | None

    @model_validator(mode="after")
    def require_source_verifier(self) -> SourceRecord:
        required_text = (
            self.source_id,
            self.title,
            self.edition,
            self.publisher_authority,
            self.internal_outcome_locator,
            self.exact_outcome_si,
            self.outcome_transcription_note,
            self.source_path,
            self.authority_note,
        )
        if any(not value.strip() for value in required_text):
            raise ValueError("source identity, edition, page context, and outcome are required")
        _require_sinhala(self.exact_outcome_si, "exact source outcome")
        if self.verification_status == "human_verified" and (
            not self.verified_by or not self.verified_on
        ):
            raise ValueError("human-verified sources require verifier identity and date")
        if self.verification_status != "human_verified" and (self.verified_by or self.verified_on):
            raise ValueError("unverified sources cannot carry approval provenance")
        return self


class SkillRecord(FrozenModel):
    skill_id: str
    skill_version: str
    name_si: str
    observable_definition: str
    prerequisites: tuple[str, ...]
    content_limits: tuple[str, ...]
    source_id: str
    lifecycle_status: Literal["draft", "approved", "retired"]
    reviewer_id: str | None
    reviewed_on: str | None

    @model_validator(mode="after")
    def validate_identity_and_language(self) -> SkillRecord:
        if not SKILL_ID_PATTERN.fullmatch(self.skill_id):
            raise ValueError("skill_id is not a stable Grade 5 Mathematics outcome ID")
        _require_sinhala(self.name_si, "skill name")
        _require_content_reviewer(self.lifecycle_status, self.reviewer_id, self.reviewed_on)
        return self


class MisconceptionRecord(FrozenModel):
    misconception_id: str
    label_si: str
    observable_evidence: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    eligible_scaffold_ids: tuple[str, ...]
    source_basis: str
    mapping_version: str
    review_status: Literal["draft", "approved"]
    reviewer_id: str | None
    reviewed_on: str | None

    @model_validator(mode="after")
    def require_reviewer(self) -> MisconceptionRecord:
        _require_content_reviewer(self.review_status, self.reviewer_id, self.reviewed_on)
        return self


class ScaffoldRecord(FrozenModel):
    scaffold_id: str
    scaffold_revision_id: str
    scaffold_type: Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]
    skill_id: str
    language: Literal["si"]
    title_si: str
    body_si: tuple[str, ...]
    visual_alt_text_si: str | None
    worked_values: tuple[int, ...]
    target_misconception_ids: tuple[str, ...]
    maximum_steps: Annotated[int, Field(ge=1, le=8)]
    withdrawal_rule: Literal["remove_before_unsupported_after"]
    answer_leakage_rule: Literal["no_probe_values_or_answers"]
    research_eligible: bool
    review_status: Literal["draft", "approved"]
    source_id: str
    source_page: Annotated[int, Field(ge=1)]
    reviewer_id: str | None
    reviewed_on: str | None

    @model_validator(mode="after")
    def validate_sinhala_and_revision(self) -> ScaffoldRecord:
        if not REVISION_ID_PATTERN.fullmatch(self.scaffold_revision_id):
            raise ValueError("scaffold_revision_id must be immutable and versioned")
        _require_sinhala(self.title_si, "scaffold title")
        for step in self.body_si:
            _require_sinhala_or_math(step, "scaffold body")
        if self.visual_alt_text_si is not None:
            _require_sinhala(self.visual_alt_text_si, "visual alternative text")
        if len(self.body_si) > self.maximum_steps:
            raise ValueError("scaffold body exceeds maximum_steps")
        _require_content_reviewer(self.review_status, self.reviewer_id, self.reviewed_on)
        return self


class PublicOption(FrozenModel):
    option_id: str
    text_si: str


class ItemRevision(FrozenModel):
    item_id: str
    revision_id: str
    skill_id: str
    grade: Literal[5]
    medium: Literal["si"]
    measurement_role: Literal[
        "unsupported_before", "supported_practice", "unsupported_after"
    ]
    assistance_allowed: bool
    prompt_si: str
    object_kind: str
    total: Annotated[int, Field(gt=0)]
    response_format: Literal["single_choice"]
    difficulty_band: Literal["introductory"]
    maximum_score: Literal[1]
    accessibility_label_si: str
    requires_color: Literal[False]
    keyboard_operable: Literal[True]
    options: tuple[PublicOption, ...]
    parallel_family_id: str
    source_id: str
    source_page: Annotated[int, Field(ge=1)]
    content_version: str
    review_status: Literal["draft", "approved"]
    reviewer_id: str | None
    reviewed_on: str | None
    rubric_review_status: Literal["pending", "approved"]
    rubric_reviewer_id: str | None
    rubric_reviewed_on: str | None

    @model_validator(mode="after")
    def validate_role_and_revision(self) -> ItemRevision:
        if not REVISION_ID_PATTERN.fullmatch(self.revision_id):
            raise ValueError("item revision IDs must be immutable and versioned")
        should_allow = self.measurement_role == "supported_practice"
        if self.assistance_allowed is not should_allow:
            raise ValueError("only supported_practice may allow assistance")
        _require_sinhala(self.prompt_si, "item prompt")
        _require_sinhala(self.accessibility_label_si, "item accessibility label")
        if len({option.option_id for option in self.options}) != len(self.options):
            raise ValueError("item option IDs must be unique")
        _require_content_reviewer(self.review_status, self.reviewer_id, self.reviewed_on)
        _require_content_reviewer(
            self.rubric_review_status,
            self.rubric_reviewer_id,
            self.rubric_reviewed_on,
        )
        return self


class ParallelFamily(FrozenModel):
    family_id: str
    skill_id: str
    revision_ids: tuple[str, ...]
    cognitive_operation: Literal["compute_half_of_even_set"]
    response_format: Literal["single_choice"]
    difficulty_band: Literal["introductory"]
    equivalence_constraints: tuple[str, ...]
    equivalence_version: str
    review_status: Literal["draft", "approved"]
    reviewer_id: str | None
    reviewed_on: str | None

    @model_validator(mode="after")
    def require_reviewer(self) -> ParallelFamily:
        _require_content_reviewer(self.review_status, self.reviewer_id, self.reviewed_on)
        return self


class PublicCurriculumPackage(FrozenModel):
    package_version: Literal[CURRICULUM_PACKAGE_VERSION]
    scope: Literal["one_atomic_grade5_sinhala_skill"]
    source: SourceRecord
    skill: SkillRecord
    misconceptions: tuple[MisconceptionRecord, ...]
    scaffolds: tuple[ScaffoldRecord, ...]
    item_revisions: tuple[ItemRevision, ...]
    parallel_family: ParallelFamily
    reviews: tuple[ReviewRecord, ...]

    @model_validator(mode="after")
    def validate_package(self) -> PublicCurriculumPackage:
        if self.skill.source_id != self.source.source_id:
            raise ValueError("skill source does not match registered source")
        if {record.review_kind for record in self.reviews} != REQUIRED_REVIEW_KINDS:
            raise ValueError("all four human review records are required")
        if "unknown_or_other" not in {row.misconception_id for row in self.misconceptions}:
            raise ValueError("misconception catalogue requires unknown_or_other")
        if {row.scaffold_type for row in self.scaffolds} != {
            "visual_guidance",
            "worked_parallel_example",
            "step_by_step_guidance",
        }:
            raise ValueError("exactly the three scaffold types are required")
        if any(row.skill_id != self.skill.skill_id for row in self.scaffolds):
            raise ValueError("scaffold references a different skill")
        if any(row.skill_id != self.skill.skill_id for row in self.item_revisions):
            raise ValueError("item revision references a different skill")
        if self.parallel_family.skill_id != self.skill.skill_id:
            raise ValueError("parallel family references a different skill")
        if any(row.source_id != self.source.source_id for row in self.scaffolds):
            raise ValueError("scaffold references an unregistered source")
        if any(row.source_id != self.source.source_id for row in self.item_revisions):
            raise ValueError("item revision references an unregistered source")
        scaffold_ids = {row.scaffold_id for row in self.scaffolds}
        misconception_ids = {row.misconception_id for row in self.misconceptions}
        if any(
            not set(row.eligible_scaffold_ids) <= scaffold_ids for row in self.misconceptions
        ):
            raise ValueError("misconception references an unknown scaffold")
        if any(
            not set(row.target_misconception_ids) <= misconception_ids for row in self.scaffolds
        ):
            raise ValueError("scaffold references an unknown misconception")
        roles = [row.measurement_role for row in self.item_revisions]
        if sorted(roles) != sorted(
            ["unsupported_before", "supported_practice", "unsupported_after"]
        ):
            raise ValueError("one immutable revision per required measurement role is required")
        revisions = [row.revision_id for row in self.item_revisions]
        if len(set(revisions)) != len(revisions):
            raise ValueError("item revisions must be distinct")
        if len({row.item_id for row in self.item_revisions}) != len(self.item_revisions):
            raise ValueError("measurement roles cannot reuse a logical item")
        scaffold_revisions = [row.scaffold_revision_id for row in self.scaffolds]
        if len(set(scaffold_revisions)) != len(scaffold_revisions):
            raise ValueError("scaffold revisions must be distinct")
        if tuple(revisions) != self.parallel_family.revision_ids:
            raise ValueError("parallel family must list every item revision in package order")
        if any(row.parallel_family_id != self.parallel_family.family_id for row in self.item_revisions):
            raise ValueError("item revision references a different parallel family")
        if len({(row.object_kind, row.total) for row in self.item_revisions}) != 3:
            raise ValueError("parallel probes require distinct surface contexts")
        probe_values = {row.total for row in self.item_revisions}
        probe_values.update(
            int(option.text_si)
            for row in self.item_revisions
            for option in row.options
            if option.text_si.isdecimal()
        )
        for scaffold in self.scaffolds:
            if probe_values.intersection(scaffold.worked_values):
                raise ValueError("scaffold reuses a probe value and could leak the answer")
        return self

    def approved_for_child_delivery(self) -> bool:
        content_approved = (
            self.skill.lifecycle_status == "approved"
            and all(row.review_status == "approved" for row in self.misconceptions)
            and all(row.review_status == "approved" for row in self.scaffolds)
            and all(row.review_status == "approved" for row in self.item_revisions)
            and all(row.rubric_review_status == "approved" for row in self.item_revisions)
            and self.parallel_family.review_status == "approved"
        )
        reviews_approved = all(row.status == "approved" for row in self.reviews)
        source_approved = (
            self.source.verification_status == "human_verified"
            and self.source.usage_rights_status == "permitted"
        )
        return content_approved and reviews_approved and source_approved


class AnswerKey(FrozenModel):
    revision_id: str
    correct_option_id: str
    accepted_response: str
    rubric: str
    scoring_version: str
    distractor_misconception_ids: dict[str, str]
    fallback_misconception_id: Literal["unknown_or_other"]
    review_status: Literal["pending", "approved"]
    reviewer_id: str | None
    reviewed_on: str | None

    @model_validator(mode="after")
    def require_reviewer(self) -> AnswerKey:
        _require_content_reviewer(self.review_status, self.reviewer_id, self.reviewed_on)
        return self


def _require_sinhala(value: str, field: str) -> None:
    if not SINHALA_PATTERN.search(value):
        raise ValueError(f"{field} must contain Sinhala Unicode")
    if not unicodedata.is_normalized("NFC", value) or "\ufffd" in value:
        raise ValueError(f"{field} must be valid NFC Sinhala Unicode")


def _require_sinhala_or_math(value: str, field: str) -> None:
    if not SINHALA_PATTERN.search(value) and not re.fullmatch(r"[0-9\s÷=]+", value):
        raise ValueError(f"{field} must contain Sinhala text or a mathematical expression")
    if not unicodedata.is_normalized("NFC", value) or "\ufffd" in value:
        raise ValueError(f"{field} must be valid NFC Unicode")


def _require_content_reviewer(
    status: str, reviewer_id: str | None, reviewed_on: str | None
) -> None:
    if status == "approved" and (not reviewer_id or not reviewed_on):
        raise ValueError("approved content requires reviewer identity and date")
    if status != "approved" and (reviewer_id or reviewed_on):
        raise ValueError("draft content cannot carry approval provenance")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_manifest(path: Path) -> None:
    manifest = _read_json(path / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("package_version") != CURRICULUM_PACKAGE_VERSION:
        raise ValueError("invalid content manifest")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise TypeError("content manifest has no file inventory")
    for name, expected in files.items():
        data = (path / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"{name} does not match the immutable manifest")


def load_curriculum_public_package(
    path: Path = CURRICULUM_CONTENT_DIRECTORY, *, allow_draft: bool = False
) -> PublicCurriculumPackage:
    _verify_manifest(path)
    package = PublicCurriculumPackage.model_validate(_read_json(path / "public_content.json"))
    if not allow_draft:
        keys = _parse_answer_keys(path)
        _validate_answer_keys(package, keys)
        rubrics_approved = all(key.review_status == "approved" for key in keys.values())
        if not package.approved_for_child_delivery() or not rubrics_approved:
            raise PermissionError(
                "draft content is blocked from child delivery pending human approval"
            )
    return package


def load_curriculum_server_answer_keys(
    path: Path = CURRICULUM_CONTENT_DIRECTORY,
) -> dict[str, AnswerKey]:
    """Load scoring material for trusted server code; never serialize this into child payloads."""
    _verify_manifest(path)
    keys = _parse_answer_keys(path)
    package = load_curriculum_public_package(path, allow_draft=True)
    _validate_answer_keys(package, keys)
    return keys


def _parse_answer_keys(path: Path) -> dict[str, AnswerKey]:
    rows = _read_json(path / "server_answer_keys.json")
    if not isinstance(rows, list):
        raise TypeError("server answer keys must be a list")
    return {row.revision_id: row for row in (AnswerKey.model_validate(value) for value in rows)}


def _validate_answer_keys(
    package: PublicCurriculumPackage, keys: dict[str, AnswerKey]
) -> None:
    revision_ids = {item.revision_id for item in package.item_revisions}
    if set(keys) != revision_ids:
        raise ValueError("server answer keys do not exactly cover public item revisions")
    for item in package.item_revisions:
        option_ids = {option.option_id for option in item.options}
        if keys[item.revision_id].correct_option_id not in option_ids:
            raise ValueError("answer key references an unknown public option")
        correct_text = next(
            option.text_si
            for option in item.options
            if option.option_id == keys[item.revision_id].correct_option_id
        )
        if item.total % 2 or keys[item.revision_id].accepted_response != str(item.total // 2):
            raise ValueError("answer key does not compute one half of the even set")
        if correct_text != keys[item.revision_id].accepted_response:
            raise ValueError("answer key disagrees with the public correct option text")
        if keys[item.revision_id].review_status != item.rubric_review_status:
            raise ValueError("private rubric review status disagrees with the public gate")
        distractors = keys[item.revision_id].distractor_misconception_ids
        if set(distractors) != option_ids - {keys[item.revision_id].correct_option_id}:
            raise ValueError("every distractor must have one server-side misconception mapping")
        known_codes = {row.misconception_id for row in package.misconceptions}
        if not set(distractors.values()) <= known_codes:
            raise ValueError("answer key references an unknown misconception")
