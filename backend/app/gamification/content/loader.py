import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, TypeVar

from app.gamification.content.records import (
    AnswerOption,
    ContentAsset,
    ContentStatus,
    ItemDefinition,
    MisconceptionDefinition,
    ParallelGroup,
    PilotContentPackage,
    PilotSkill,
    ResponseFormat,
    ScaffoldDefinition,
    ScaffoldType,
    SourceReference,
    StructuredErrorMapping,
    TemplateRule,
)
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY
from app.gamification.domain.types import SupportActionType
from app.gamification.modeling.support_selection.reference_table import (
    ReferencePolicyRow,
    ReferencePolicyTable,
)
from app.gamification.skill_catalogue.contracts import ReviewStatus, SkillReview, SourceCitation

PILOT_CONTENT_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "grade5-pilot-slice" / "v1"
PACKAGE_NAME = "grade5-pilot-slice"
Record = TypeVar("Record")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _verify_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("package") != PACKAGE_NAME:
        raise ValueError("not a Grade 5 pilot content package")
    for name, metadata in manifest["files"].items():
        data = (path / name).read_bytes()
        if len(data) != metadata["bytes"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            raise ValueError(f"pilot content file {name} does not match its manifest hash")
    return manifest


def _index(records: Iterable[Record], key: Callable[[Record], str], kind: str) -> dict[str, Record]:
    indexed: dict[str, Record] = {}
    for record in records:
        identifier = key(record)
        if identifier in indexed:
            raise ValueError(f"duplicate {kind} {identifier}")
        indexed[identifier] = record
    return indexed


def _reference(row: Mapping[str, Any]) -> SourceReference:
    return SourceReference(str(row["source_id"]), str(row["page"]), str(row["curriculum_node_id"]))


def _skill(row: Mapping[str, Any]) -> PilotSkill:
    review = SkillReview(
        skill_code=row["skill_code"],
        stable_index=row["stable_index"],
        taxonomy_version=row["taxonomy_version"],
        domain=row["domain"],
        grade=row["grade"],
        status=ReviewStatus(row["status"]),
        development_only=row["development_only"],
        learner_medium=row["learner_medium"],
        required_label_languages=tuple(row["required_label_languages"]),
        deferred_languages=tuple(row["deferred_languages"]),
        scope_note=row["scope_note"],
        definition=row["definition"],
        labels=row["labels"],
        prerequisites=tuple(row["prerequisites"]),
        observable_success=tuple(row["observable_success"]),
        misconceptions=tuple(row["misconceptions"]),
        distinguishing_evidence=tuple(row["distinguishing_evidence"]),
        eligible_support_action_types=tuple(
            SupportActionType(value) for value in row["eligible_support_action_types"]
        ),
        verification_pair_rules=row["verification_pair_rules"],
        source_citations=tuple(
            SourceCitation(
                source_id=citation["source_id"],
                page_from=citation["page_from"],
                page_to=citation["page_to"],
                skill_candidate_ids=tuple(citation["skill_candidate_ids"]),
            )
            for citation in row["source_citations"]
        ),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
        superseded_by=row["superseded_by"],
    )
    return PilotSkill(
        review=review,
        universal_skill_id=row["universal_skill_id"],
        crosswalk_version=row["crosswalk_version"],
        curriculum_node_ids=tuple(row["curriculum_node_ids"]),
        id_status=row["id_status"],
    )


def _misconception(row: Mapping[str, Any]) -> MisconceptionDefinition:
    return MisconceptionDefinition(
        code=row["misconception_code"],
        skill_ids=tuple(row["skill_ids"]),
        label_si=row["label_si"],
        label_en=row["label_en"],
        description=row["description"],
        observable_error_patterns=tuple(row["observable_error_patterns"]),
        distinguishing_evidence=tuple(row["distinguishing_evidence"]),
        remediation_notes=tuple(row["remediation_notes"]),
        catalogue_version=row["catalogue_version"],
        authoring_basis=row["authoring_basis"]["kind"],
        reserved=row["reserved"],
        status=ContentStatus(row["approval_status"]),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
    )


def _item(row: Mapping[str, Any]) -> ItemDefinition:
    return ItemDefinition(
        item_id=row["item_id"],
        skill_id=row["skill_id"],
        grade=row["grade"],
        medium=row["medium"],
        item_type=row["item_type"],
        response_format=ResponseFormat(row["response_format"]),
        cognitive_operation=row["cognitive_operation"],
        question_text=row["question_text"],
        prompt_en=row["prompt_en"],
        stimulus=row["stimulus"],
        answer_options=tuple(
            AnswerOption(
                option_id=option["option_id"],
                text=option["text"],
                text_en=option["text_en"],
                misconception_code=option["misconception_code"],
                alternative_misconception_codes=tuple(option["alternative_misconception_codes"]),
                stimulus=option.get("stimulus"),
                correct_group=option.get("correct_group"),
            )
            for option in row["answer_options"]
        ),
        correct_option_id=row["correct_option_id"],
        difficulty=row["difficulty"],
        compatible_templates=tuple(row["compatible_templates"]),
        default_template=row["default_template"],
        available_scaffold_ids=tuple(row["available_scaffold_ids"]),
        parallel_group_id=row["parallel_group_id"],
        source_reference=_reference(row["source_reference"]),
        content_version=row["content_version"],
        status=ContentStatus(row["review_status"]),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
    )


def _group(row: Mapping[str, Any]) -> ParallelGroup:
    return ParallelGroup(
        parallel_group_id=row["parallel_group_id"],
        skill_id=row["skill_id"],
        item_type=row["item_type"],
        difficulty_band=row["difficulty_band"],
        response_format=ResponseFormat(row["response_format"]),
        cognitive_operation=row["cognitive_operation"],
        item_ids=tuple(row["item_ids"]),
        equivalence_version=row["equivalence_version"],
        status=ContentStatus(row["review_status"]),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
    )


def _scaffold(row: Mapping[str, Any]) -> ScaffoldDefinition:
    return ScaffoldDefinition(
        scaffold_id=row["scaffold_id"],
        scaffold_type=ScaffoldType(row["scaffold_type"]),
        skill_ids=tuple(row["skill_ids"]),
        target_misconception_ids=tuple(row["target_misconception_ids"]),
        assistance_level=row["assistance_level"],
        content_asset_id=row["content_asset_id"],
        maximum_duration_ms=row["maximum_duration_ms"],
        maximum_number_of_steps=row["maximum_number_of_steps"],
        answer_leakage_rules=tuple(row["answer_leakage_rules"]),
        withdrawal_rule=row["withdrawal_rule"],
        language=row["language"],
        version=row["version"],
        limits_status=row["limits_status"],
        status=ContentStatus(row["approval_status"]),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
    )


def _asset(row: Mapping[str, Any]) -> ContentAsset:
    return ContentAsset(
        content_asset_id=row["content_asset_id"],
        scaffold_type=ScaffoldType(row["scaffold_type"]),
        skill_id=row["skill_id"],
        language=row["language"],
        title_si=row["title_si"],
        title_en=row["title_en"],
        body_si=tuple(row["body_si"]),
        body_en=tuple(row["body_en"]),
        diagram=row["diagram"],
        source_reference=_reference(row["source_reference"]),
        status=ContentStatus(row["approval_status"]),
        reviewer_id=row["reviewer_id"],
        reviewed_on=row["reviewed_on"],
    )


def _template(row: Mapping[str, Any]) -> TemplateRule:
    return TemplateRule(
        item_type=row["item_type"],
        compatible_templates=tuple(row["compatible_templates"]),
        response_formats=tuple(ResponseFormat(value) for value in row["response_formats"]),
        table_version=row["table_version"],
    )


def _error_mapping(row: Mapping[str, Any]) -> StructuredErrorMapping:
    return StructuredErrorMapping(
        structured_error_code=row["structured_error_code"],
        misconception_code=row["misconception_code"],
        alternative_misconception_codes=tuple(row["alternative_misconception_codes"]),
        item_id=row["item_id"],
        option_id=row["option_id"],
        pattern_code=row["pattern_code"],
        mapping_version=row["mapping_version"],
    )


def _check_references(package: PilotContentPackage) -> None:
    for item in package.items.values():
        if item.skill_id not in package.skills:
            raise ValueError(f"{item.item_id} references an unknown skill")
        group = package.parallel_groups.get(item.parallel_group_id)
        if group is None or item.item_id not in group.item_ids:
            raise ValueError(f"{item.item_id} is not listed in its parallel group")
        rule = package.template_rules.get(item.item_type)
        if rule is None or not set(item.compatible_templates) <= set(rule.compatible_templates):
            raise ValueError(f"{item.item_id} templates are not allowed for its item type")
        for scaffold_id in item.available_scaffold_ids:
            if scaffold_id not in package.scaffolds:
                raise ValueError(f"{item.item_id} references an unknown scaffold")
        for option in item.answer_options:
            codes = (option.misconception_code, *option.alternative_misconception_codes)
            if any(code is not None and code not in package.misconceptions for code in codes):
                raise ValueError(f"{item.item_id} references an unknown misconception")
    for group in package.parallel_groups.values():
        if any(item_id not in package.items for item_id in group.item_ids):
            raise ValueError(f"{group.parallel_group_id} references an unknown item")
    for scaffold in package.scaffolds.values():
        asset = package.content_assets.get(scaffold.content_asset_id)
        if asset is None or asset.scaffold_type is not scaffold.scaffold_type:
            raise ValueError(f"{scaffold.scaffold_id} has no matching content asset")
        if any(code not in package.misconceptions for code in scaffold.target_misconception_ids):
            raise ValueError(f"{scaffold.scaffold_id} targets an unknown misconception")
    for mapping in package.error_mappings.values():
        if mapping.misconception_code not in package.misconceptions:
            raise ValueError(f"{mapping.structured_error_code} maps to an unknown misconception")


def _unapproved(package: PilotContentPackage) -> int:
    records: list[ContentStatus] = [
        *(
            ContentStatus.APPROVED
            if skill.review.status is ReviewStatus.APPROVED
            else ContentStatus.DRAFT
            for skill in package.skills.values()
        ),
        *(record.status for record in package.misconceptions.values()),
        *(record.status for record in package.items.values()),
        *(record.status for record in package.parallel_groups.values()),
        *(record.status for record in package.scaffolds.values()),
        *(record.status for record in package.content_assets.values()),
    ]
    return sum(status is not ContentStatus.APPROVED for status in records)


def _reference_policy(rows: list[dict[str, Any]], version: str) -> ReferencePolicyTable:
    parsed = []
    for row in rows:
        if row["table_version"] != version:
            raise ValueError("reference policy row version does not match the package")
        parsed.append(
            ReferencePolicyRow(
                skill_id=row["skill_id"],
                top_misconception_code=row["top_misconception_code"],
                preferred_scaffold_type=row["preferred_scaffold_type"],
                rule=row["rule"],
                authoring_basis=row["authoring_basis"],
            )
        )
    return ReferencePolicyTable(version=version, rows=tuple(parsed))


def load_pilot_content_package(
    path: Path = PILOT_CONTENT_DIRECTORY, *, allow_draft: bool = False
) -> PilotContentPackage:
    """Load the pilot slice; fail closed unless every record is approved or drafts are allowed."""
    manifest = _verify_manifest(path)
    package = PilotContentPackage(
        package_version=manifest["version"],
        versions=manifest["versions"],
        skills=_index(
            map(_skill, _read_jsonl(path / "skills.jsonl")), lambda r: r.skill_id, "skill"
        ),
        misconceptions=_index(
            map(_misconception, _read_jsonl(path / "misconception_catalogue.jsonl")),
            lambda r: r.code,
            "misconception",
        ),
        items=_index(map(_item, _read_jsonl(path / "items.jsonl")), lambda r: r.item_id, "item"),
        parallel_groups=_index(
            map(_group, _read_jsonl(path / "parallel_groups.jsonl")),
            lambda r: r.parallel_group_id,
            "parallel group",
        ),
        scaffolds=_index(
            map(_scaffold, _read_jsonl(path / "scaffolds.jsonl")),
            lambda r: r.scaffold_id,
            "scaffold",
        ),
        content_assets=_index(
            map(_asset, _read_jsonl(path / "content_assets.jsonl")),
            lambda r: r.content_asset_id,
            "content asset",
        ),
        template_rules=_index(
            map(_template, _read_jsonl(path / "template_compatibility.jsonl")),
            lambda r: r.item_type,
            "template rule",
        ),
        error_mappings=_index(
            map(_error_mapping, _read_jsonl(path / "structured_error_mappings.jsonl")),
            lambda r: r.structured_error_code,
            "structured error code",
        ),
        reference_policy=_reference_policy(
            _read_jsonl(path / "reference_policy_table.jsonl"),
            str(manifest["versions"]["reference_policy_version"]),
        ),
    )
    _check_references(package)
    unapproved = _unapproved(package)
    if unapproved and not allow_draft:
        raise PermissionError(
            f"{unapproved} pilot content records are not approved; pass allow_draft=True for development"
        )
    return package
