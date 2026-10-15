"""Validate and freeze the hand-authored Grade 5 Fractions pilot slice (correction phase C1).

Authored JSONL files are the source of truth. This tool checks them against the shared curriculum
trace and source registry, the Universal Skill Node crosswalk, and the C1 content rules, then
writes the derived error-mapping table, readiness gates, schema, README and manifest. Nothing is
approved here: every record stays draft until a named reviewer approves it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adaptive_tutor.infrastructure.skill_taxonomy import (  # noqa: E402
    XlsxSkillTaxonomyCatalog,
)

DEFAULT_PACKAGE_DIR = PROJECT_ROOT / "data/gamification/grade5-pilot-slice/v1"
TRACE_DIR = PROJECT_ROOT / "data/curriculum/grade5-curriculum-trace/v1"
REGISTRY_PATH = PROJECT_ROOT / "data/curriculum/registry/v1/sources.jsonl"
CROSSWALK_PATH = (
    PROJECT_ROOT / "data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl"
)
V2_SKILL_CANDIDATES = (
    PROJECT_ROOT / "data/gamification/grade5-curriculum-game-dataset/v2/skill_candidates.jsonl"
)
TAXONOMY_WORKBOOK = PROJECT_ROOT / "docs/skill_nodes.xlsx"

PACKAGE = "grade5-pilot-slice"
PACKAGE_VERSION = "1.0.0"
VERSIONS = {
    "skill_taxonomy_version": "grade5-pilot-skills-v1",
    "crosswalk_version": "grade5-universal-crosswalk-v1",
    "catalogue_version": "grade5-pilot-misconceptions-v1",
    "content_version": "grade5-pilot-content-v1",
    "scaffold_version": "grade5-pilot-scaffolds-v1",
    "equivalence_version": "grade5-pilot-equivalence-v1",
    "template_table_version": "grade5-pilot-templates-v1",
    "error_mapping_version": "grade5-pilot-error-map-v1",
    "reference_policy_version": "authored-reference-policy-v1",
}
REFERENCE_POLICY_JSONL = "reference_policy_table.jsonl"
AUTHORED_FILES = (
    "skills.jsonl",
    "misconception_catalogue.jsonl",
    "items.jsonl",
    "parallel_groups.jsonl",
    "scaffolds.jsonl",
    "content_assets.jsonl",
    "template_compatibility.jsonl",
    "source_documents.jsonl",
)
GENERATED_JSONL = "structured_error_mappings.jsonl"
UNIVERSAL_SKILL_ID = "MAT-FRC"
UNIVERSAL_SKILL_ID_MAX_LENGTH = 16
RESERVED_CODES = ("unknown/other", "careless/other")
CANONICAL_ARMS = ("visual_guidance", "worked_example", "step_by_step_guidance")
SCAFFOLD_TYPES = (*CANONICAL_ARMS, "concept_reminder")
TEMPLATES = ("choice_quest", "sort_and_group", "build_manipulate")
REVIEW_STATES = ("draft", "approved", "retired")
SKILL_COUNT_RANGE = (5, 10)
MISCONCEPTIONS_PER_SKILL = (3, 5)
MIN_GROUPS_PER_SKILL = 2
MIN_ITEMS_PER_GROUP = 3
SURFACE_KEYS = ("total", "shaded", "tenths", "target_numerator", "answer", "unit_answer")
SINHALA = re.compile(r"[\u0D80-\u0DFF]")
ARITHMETIC_STEP = re.compile(r"[\d\s÷×+\-=./]+")
PATTERN_CODES = (
    {
        "pattern_code": "numeric_construction:unanticipated_value",
        "response_format": "numeric_construction",
        "misconception_code": "unknown/other",
    },
    {
        "pattern_code": "binary_sort:multiple_misplacements",
        "response_format": "binary_sort",
        "misconception_code": "unknown/other",
    },
    {
        "pattern_code": "any:no_response",
        "response_format": None,
        "misconception_code": "unknown/other",
    },
)

_STRING = {"type": "string", "minLength": 1}
_NULLABLE_STRING = {"type": ["string", "null"]}
_STRINGS = {"type": "array", "items": _STRING}
_REVIEW = {"type": "string", "enum": list(REVIEW_STATES)}
_SOURCE_REFERENCE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_id", "page", "curriculum_node_id"],
    "properties": {"source_id": _STRING, "page": _STRING, "curriculum_node_id": _STRING},
}
_REVIEWER = {"reviewer_id": _NULLABLE_STRING, "reviewed_on": _NULLABLE_STRING}


def _record(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(properties),
        "properties": properties,
    }


RECORD_SCHEMAS: dict[str, dict[str, Any]] = {
    "skills.jsonl": _record(
        {
            "skill_code": _STRING,
            "stable_index": {"type": "integer", "minimum": 0},
            "taxonomy_version": {"type": "string", "enum": [VERSIONS["skill_taxonomy_version"]]},
            "domain": {"type": "string", "enum": ["MAT"]},
            "grade": {"type": "integer", "enum": [5]},
            "status": _REVIEW,
            "development_only": {"type": "boolean"},
            "learner_medium": {"type": "string", "enum": ["si"]},
            "required_label_languages": _STRINGS,
            "deferred_languages": _STRINGS,
            "scope_note": _STRING,
            "definition": _STRING,
            "labels": {"type": "object"},
            "prerequisites": _STRINGS,
            "observable_success": {**_STRINGS, "minItems": 1},
            "misconceptions": _STRINGS,
            "distinguishing_evidence": {**_STRINGS, "minItems": 1},
            "eligible_support_action_types": _STRINGS,
            "verification_pair_rules": {"type": "object"},
            "source_citations": {
                "type": "array",
                "minItems": 1,
                "items": _record(
                    {
                        "source_id": _STRING,
                        "page_from": _STRING,
                        "page_to": _STRING,
                        "skill_candidate_ids": {**_STRINGS, "minItems": 1},
                    }
                ),
            },
            "superseded_by": _NULLABLE_STRING,
            "universal_skill_id": _STRING,
            "crosswalk_version": {"type": "string", "enum": [VERSIONS["crosswalk_version"]]},
            "curriculum_node_ids": {**_STRINGS, "minItems": 1},
            "id_status": {
                "type": "string",
                "enum": ["v2_candidate", "pilot_only_pending_trace_correction"],
            },
            **_REVIEWER,
        }
    ),
    "misconception_catalogue.jsonl": _record(
        {
            "misconception_code": _STRING,
            "skill_ids": {**_STRINGS, "minItems": 1},
            "label_si": _STRING,
            "label_en": _STRING,
            "description": _STRING,
            "observable_error_patterns": {**_STRINGS, "minItems": 1},
            "distinguishing_evidence": {**_STRINGS, "minItems": 1},
            "remediation_notes": {**_STRINGS, "minItems": 1},
            "catalogue_version": {"type": "string", "enum": [VERSIONS["catalogue_version"]]},
            "authoring_basis": _record(
                {
                    "kind": {
                        "type": "string",
                        "enum": ["curriculum_page", "literature", "researcher_hypothesis"],
                    },
                    "source_id": _NULLABLE_STRING,
                    "page": _NULLABLE_STRING,
                    "note": _STRING,
                }
            ),
            "reserved": {"type": "boolean"},
            "approval_status": _REVIEW,
            **_REVIEWER,
        }
    ),
    "items.jsonl": _record(
        {
            "item_id": _STRING,
            "skill_id": _STRING,
            "grade": {"type": "integer", "enum": [5]},
            "medium": {"type": "string", "enum": ["si"]},
            "item_type": _STRING,
            "response_format": {
                "type": "string",
                "enum": ["single_choice", "binary_sort", "numeric_construction"],
            },
            "cognitive_operation": _STRING,
            "question_text": _STRING,
            "prompt_en": _STRING,
            "stimulus": {"type": ["object", "null"]},
            "answer_options": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "option_id",
                        "text",
                        "text_en",
                        "misconception_code",
                        "alternative_misconception_codes",
                    ],
                    "properties": {
                        "option_id": _STRING,
                        "text": _STRING,
                        "text_en": _STRING,
                        "misconception_code": _NULLABLE_STRING,
                        "alternative_misconception_codes": _STRINGS,
                        "stimulus": {"type": "object"},
                        "correct_group": {"type": "string", "enum": ["yes", "no"]},
                    },
                },
            },
            "correct_option_id": _NULLABLE_STRING,
            "response_groups": {"type": ["array", "null"]},
            "parameters": {"type": "object"},
            "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
            "compatible_templates": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(TEMPLATES)},
            },
            "default_template": {"type": "string", "enum": list(TEMPLATES)},
            "available_scaffold_ids": {**_STRINGS, "minItems": 3},
            "parallel_group_id": _STRING,
            "source_reference": _SOURCE_REFERENCE,
            "authoring_basis": {"type": "string", "enum": ["researcher_authored"]},
            "content_version": {"type": "string", "enum": [VERSIONS["content_version"]]},
            "review_status": _REVIEW,
            **_REVIEWER,
        }
    ),
    "parallel_groups.jsonl": _record(
        {
            "parallel_group_id": _STRING,
            "skill_id": _STRING,
            "item_type": _STRING,
            "difficulty_band": _STRING,
            "response_format": _STRING,
            "cognitive_operation": _STRING,
            "item_ids": {**_STRINGS, "minItems": MIN_ITEMS_PER_GROUP},
            "equivalence_note": _STRING,
            "equivalence_version": {"type": "string", "enum": [VERSIONS["equivalence_version"]]},
            "review_status": _REVIEW,
            **_REVIEWER,
        }
    ),
    "scaffolds.jsonl": _record(
        {
            "scaffold_id": _STRING,
            "scaffold_type": {"type": "string", "enum": list(SCAFFOLD_TYPES)},
            "skill_ids": {**_STRINGS, "minItems": 1},
            "target_misconception_ids": {**_STRINGS, "minItems": 1},
            "assistance_level": {"type": "integer", "minimum": 1, "maximum": 3},
            "content_asset_id": _STRING,
            "maximum_duration_ms": {"type": "integer", "minimum": 1},
            "maximum_number_of_steps": {"type": "integer", "minimum": 1},
            "answer_leakage_rules": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": ["different_values_required", "no_final_answer"],
                },
            },
            "withdrawal_rule": {"type": "string", "enum": ["remove_before_verification"]},
            "language": {"type": "string", "enum": ["si"]},
            "version": {"type": "string", "enum": [VERSIONS["scaffold_version"]]},
            "limits_status": {"type": "string", "enum": ["provisional_assumption", "reviewed"]},
            "approval_status": _REVIEW,
            **_REVIEWER,
        }
    ),
    "content_assets.jsonl": _record(
        {
            "content_asset_id": _STRING,
            "scaffold_type": {"type": "string", "enum": list(SCAFFOLD_TYPES)},
            "skill_id": _STRING,
            "language": {"type": "string", "enum": ["si"]},
            "title_si": _STRING,
            "title_en": _STRING,
            "body_si": {**_STRINGS, "minItems": 1},
            "body_en": {**_STRINGS, "minItems": 1},
            "diagram": {"type": ["object", "null"]},
            "parameters": {"type": "object"},
            "source_reference": _SOURCE_REFERENCE,
            "authoring_basis": {"type": "string", "enum": ["researcher_authored"]},
            "content_version": {"type": "string", "enum": [VERSIONS["content_version"]]},
            "approval_status": _REVIEW,
            **_REVIEWER,
        }
    ),
    "template_compatibility.jsonl": _record(
        {
            "item_type": _STRING,
            "specification_category": _STRING,
            "compatible_templates": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(TEMPLATES)},
            },
            "response_formats": {**_STRINGS, "minItems": 1},
            "table_version": {"type": "string", "enum": [VERSIONS["template_table_version"]]},
        }
    ),
    "source_documents.jsonl": _record(
        {
            "source_id": _STRING,
            "file_name": _STRING,
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "pdf_page_count": {"type": "integer", "minimum": 1},
            "printed_page_offset": {"type": "integer", "minimum": 0},
            "printed_last_page": {"type": "integer", "minimum": 1},
            "pages_checked": {**_STRINGS, "minItems": 1},
            "check_note": _STRING,
        }
    ),
    GENERATED_JSONL: _record(
        {
            "item_id": _NULLABLE_STRING,
            "option_id": _NULLABLE_STRING,
            "pattern_code": _NULLABLE_STRING,
            "skill_id": _NULLABLE_STRING,
            "response_format": _NULLABLE_STRING,
            "misconception_code": _STRING,
            "alternative_misconception_codes": _STRINGS,
            "structured_error_code": _STRING,
            "mapping_version": {"type": "string", "enum": [VERSIONS["error_mapping_version"]]},
            "review_status": _REVIEW,
        }
    ),
    REFERENCE_POLICY_JSONL: _record(
        {
            "table_version": {"type": "string", "enum": [VERSIONS["reference_policy_version"]]},
            "skill_id": _STRING,
            "top_misconception_code": _STRING,
            "preferred_scaffold_type": {"type": "string", "enum": list(CANONICAL_ARMS)},
            "authoring_basis": {"type": "string", "enum": ["provisional_assumption"]},
            "rule": {
                "type": "string",
                "enum": [
                    "lowest_assistance_among_scaffolds_targeting_code",
                    "least_assistance_scaffold_for_reserved_code",
                ],
            },
        }
    ),
}
_JSON_TYPES = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def schema_errors(value: Any, schema: Mapping[str, Any], path: str) -> list[str]:
    """Check the subset of JSON Schema used by RECORD_SCHEMAS."""
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        matches = any(
            isinstance(value, _JSON_TYPES[name])
            and not (name == "integer" and isinstance(value, bool))
            for name in names
        )
        if not matches:
            return [f"{path}: expected {'/'.join(names)}"]
    errors: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: empty string")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            errors.append(f"{path}: {value} is out of range")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} entries")
        for index, entry in enumerate(value):
            errors.extend(schema_errors(entry, schema.get("items", {}), f"{path}[{index}]"))
    if isinstance(value, dict) and "properties" in schema:
        missing = [key for key in schema.get("required", ()) if key not in value]
        errors.extend(f"{path}: missing {key}" for key in missing)
        if schema.get("additionalProperties") is False:
            errors.extend(
                f"{path}: unexpected {key}" for key in value if key not in schema["properties"]
            )
        for key, entry in value.items():
            if key in schema["properties"]:
                errors.extend(schema_errors(entry, schema["properties"][key], f"{path}.{key}"))
    return errors


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def render_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def page_number(page: str) -> int | None:
    return int(page) if page.isdigit() else None


def load_context() -> dict[str, Any]:
    trace_nodes = {
        row["curriculum_node_id"]: row for row in read_jsonl(TRACE_DIR / "curriculum_nodes.jsonl")
    }
    return {
        "registry_ids": {row["source_id"] for row in read_jsonl(REGISTRY_PATH)},
        "trace_nodes": trace_nodes,
        "v2_skill_ids": {row["skill_candidate_id"] for row in read_jsonl(V2_SKILL_CANDIDATES)},
        "crosswalk": {
            row["gamification_skill_id"]: row["universal_skill_id"]
            for row in read_jsonl(CROSSWALK_PATH)
        },
        "taxonomy_ids": {
            node.skill_id for node in XlsxSkillTaxonomyCatalog(TAXONOMY_WORKBOOK).load()
        },
    }


def load_authored(package_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return {name: read_jsonl(package_dir / name) for name in AUTHORED_FILES}


def surface_values(parameters: Mapping[str, Any]) -> set[int]:
    values = {int(parameters[key]) for key in SURFACE_KEYS if key in parameters}
    if parameters.get("answer_form") == "count":
        values.add(parameters["total"] * parameters["numerator"] // parameters["denominator"])
    return values


def expected_correct_text(item: Mapping[str, Any]) -> str | None:
    parameters = item["parameters"]
    form = parameters.get("answer_form")
    if form == "count":
        total, numerator, denominator = (
            parameters[key] for key in ("total", "numerator", "denominator")
        )
        if (total * numerator) % denominator:
            return None
        return str(total * numerator // denominator)
    if form == "fraction" and "parts" in parameters:
        return f"{parameters['shaded']}/{parameters['parts']}"
    if form == "fraction" and "tenths" in parameters:
        return f"{parameters['tenths']}/10"
    if form == "decimal":
        return f"0.{parameters['tenths']}"
    return None


def shows_target(stimulus: Mapping[str, Any] | None, parameters: Mapping[str, Any]) -> bool:
    return bool(
        stimulus
        and stimulus.get("equal_parts") is True
        and stimulus.get("parts") == parameters["target_denominator"]
        and stimulus.get("shaded_parts") == parameters["target_numerator"]
    )


def check_reference(
    owner: str,
    reference: Mapping[str, Any],
    allowed_nodes: set[str],
    context: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    source_id, page, node_id = (
        reference["source_id"],
        reference["page"],
        reference["curriculum_node_id"],
    )
    node = context["trace_nodes"].get(node_id)
    if source_id not in context["registry_ids"]:
        errors.append(f"{owner}: {source_id} is not in the shared source registry")
    if node is None:
        errors.append(f"{owner}: curriculum node {node_id} is not in the shared trace")
        return
    if node_id not in allowed_nodes:
        errors.append(f"{owner}: {node_id} is not one of the skill's curriculum nodes")
    if node["source_id"] != source_id:
        errors.append(f"{owner}: {node_id} belongs to {node['source_id']}, not {source_id}")
    number = page_number(page)
    low, high = page_number(node["source_page_from"]), page_number(node["source_page_to"])
    if number is None or low is None or high is None or not low <= number <= high:
        errors.append(
            f"{owner}: page {page} is outside {node_id} pages {node['source_page_from']}-{node['source_page_to']}"
        )
    document = documents.get(source_id)
    if document and number is not None and number > document["printed_last_page"]:
        errors.append(f"{owner}: page {page} is beyond the last printed page of {source_id}")


def validate(authored: Mapping[str, list[dict[str, Any]]], context: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, rows in authored.items():
        for index, row in enumerate(rows):
            errors.extend(schema_errors(row, RECORD_SCHEMAS[name], f"{name}[{index}]"))
    if errors:
        return errors

    skills = {row["skill_code"]: row for row in authored["skills.jsonl"]}
    catalogue = {
        row["misconception_code"]: row for row in authored["misconception_catalogue.jsonl"]
    }
    items = {row["item_id"]: row for row in authored["items.jsonl"]}
    groups = {row["parallel_group_id"]: row for row in authored["parallel_groups.jsonl"]}
    scaffolds = {row["scaffold_id"]: row for row in authored["scaffolds.jsonl"]}
    assets = {row["content_asset_id"]: row for row in authored["content_assets.jsonl"]}
    templates = {row["item_type"]: row for row in authored["template_compatibility.jsonl"]}
    documents = {row["source_id"]: row for row in authored["source_documents.jsonl"]}
    for name, key, mapping in (
        ("skills.jsonl", "skill_code", skills),
        ("misconception_catalogue.jsonl", "misconception_code", catalogue),
        ("items.jsonl", "item_id", items),
        ("parallel_groups.jsonl", "parallel_group_id", groups),
        ("scaffolds.jsonl", "scaffold_id", scaffolds),
        ("content_assets.jsonl", "content_asset_id", assets),
        ("template_compatibility.jsonl", "item_type", templates),
        ("source_documents.jsonl", "source_id", documents),
    ):
        if len(mapping) != len(authored[name]):
            errors.append(f"{name}: duplicate {key}")

    for name, status_field, key in (
        ("misconception_catalogue.jsonl", "approval_status", "misconception_code"),
        ("parallel_groups.jsonl", "review_status", "parallel_group_id"),
        ("content_assets.jsonl", "approval_status", "content_asset_id"),
    ):
        for row in authored[name]:
            if row[status_field] != "draft" and (not row["reviewer_id"] or not row["reviewed_on"]):
                errors.append(
                    f"{name.removesuffix('.jsonl')}: {row[key]} is not draft but has no reviewer"
                )

    for source_id in documents:
        if source_id not in context["registry_ids"]:
            errors.append(f"source_documents: {source_id} is not in the shared source registry")

    if not SKILL_COUNT_RANGE[0] <= len(skills) <= SKILL_COUNT_RANGE[1]:
        errors.append(
            f"skills: expected {SKILL_COUNT_RANGE[0]}-{SKILL_COUNT_RANGE[1]} skills, found {len(skills)}"
        )
    if sorted(row["stable_index"] for row in skills.values()) != list(range(len(skills))):
        errors.append("skills: stable_index values must be 0..n-1")

    for code in RESERVED_CODES:
        if code not in catalogue or not catalogue[code]["reserved"]:
            errors.append(f"misconception_catalogue: reserved code {code} is missing")
    for code, row in catalogue.items():
        if row["reserved"] != (code in RESERVED_CODES):
            errors.append(f"misconception_catalogue: {code} has the wrong reserved flag")
        if not row["reserved"] and not re.fullmatch(r"MAT-FRC-M\d{2}", code):
            errors.append(f"misconception_catalogue: {code} does not use the MAT-FRC-Mnn pattern")
        if not SINHALA.search(row["label_si"]):
            errors.append(f"misconception_catalogue: {code} label_si is not Sinhala")
        basis = row["authoring_basis"]
        if basis["kind"] == "curriculum_page":
            if basis["source_id"] not in context["registry_ids"] or not basis["page"]:
                errors.append(f"misconception_catalogue: {code} cites an unknown curriculum page")
        for skill_id in row["skill_ids"]:
            if skill_id not in skills:
                errors.append(
                    f"misconception_catalogue: {code} references unknown skill {skill_id}"
                )

    skill_codes_by_skill: dict[str, set[str]] = defaultdict(set)
    for code, row in catalogue.items():
        if not row["reserved"]:
            for skill_id in row["skill_ids"]:
                skill_codes_by_skill[skill_id].add(code)

    for skill_id, row in skills.items():
        if row["id_status"] == "v2_candidate":
            if skill_id not in context["v2_skill_ids"]:
                errors.append(f"skills: {skill_id} is not a v2 skill candidate")
            expected_parent = context["crosswalk"].get(skill_id)
        else:
            if skill_id in context["v2_skill_ids"]:
                errors.append(f"skills: {skill_id} is a v2 candidate but marked pilot-only")
            parent_candidate = skill_id.rsplit("-", 1)[0]
            expected_parent = context["crosswalk"].get(parent_candidate)
        universal = row["universal_skill_id"]
        if universal != expected_parent or universal != UNIVERSAL_SKILL_ID:
            errors.append(
                f"skills: {skill_id} parent {universal} disagrees with the crosswalk ({expected_parent})"
            )
        if (
            universal not in context["taxonomy_ids"]
            or len(universal) > UNIVERSAL_SKILL_ID_MAX_LENGTH
        ):
            errors.append(
                f"skills: {skill_id} parent {universal} is not a valid Universal Skill Node"
            )
        if row["status"] != "draft" and (not row["reviewer_id"] or not row["reviewed_on"]):
            errors.append(f"skills: {skill_id} is not draft but has no reviewer")
        if not SINHALA.search(row["labels"].get("si") or ""):
            errors.append(f"skills: {skill_id} has no Sinhala label")
        if set(row["misconceptions"]) != skill_codes_by_skill[skill_id]:
            errors.append(f"skills: {skill_id} misconception list disagrees with the catalogue")
        if (
            not MISCONCEPTIONS_PER_SKILL[0]
            <= len(skill_codes_by_skill[skill_id])
            <= MISCONCEPTIONS_PER_SKILL[1]
        ):
            errors.append(
                f"skills: {skill_id} needs {MISCONCEPTIONS_PER_SKILL[0]}-{MISCONCEPTIONS_PER_SKILL[1]} misconceptions"
            )
        for prerequisite in row["prerequisites"]:
            if prerequisite not in skills:
                errors.append(
                    f"skills: {skill_id} prerequisite {prerequisite} is not a pilot skill"
                )
        nodes = set(row["curriculum_node_ids"])
        for node_id in nodes:
            if node_id not in context["trace_nodes"]:
                errors.append(f"skills: {skill_id} cites unknown curriculum node {node_id}")
        for citation in row["source_citations"]:
            if citation["source_id"] not in context["registry_ids"]:
                errors.append(f"skills: {skill_id} cites unknown source {citation['source_id']}")
            if citation["skill_candidate_ids"] != [skill_id]:
                errors.append(f"skills: {skill_id} citation must name only this skill")
            low, high = page_number(citation["page_from"]), page_number(citation["page_to"])
            covering = [
                context["trace_nodes"][node_id]
                for node_id in nodes
                if node_id in context["trace_nodes"]
                and context["trace_nodes"][node_id]["source_id"] == citation["source_id"]
            ]
            within = (
                low is not None
                and high is not None
                and low <= high
                and any(
                    page_number(node["source_page_from"]) is not None
                    and page_number(node["source_page_to"]) is not None
                    and page_number(node["source_page_from"]) <= low
                    and high <= page_number(node["source_page_to"])
                    for node in covering
                )
            )
            if not within:
                errors.append(
                    f"skills: {skill_id} citation {citation['source_id']} p.{citation['page_from']}-"
                    f"{citation['page_to']} is not inside one of its curriculum nodes"
                )

    group_counts: Counter[str] = Counter()
    for group_id, group in groups.items():
        skill_id = group["skill_id"]
        if skill_id not in skills:
            errors.append(f"parallel_groups: {group_id} references unknown skill {skill_id}")
            continue
        if len(group["item_ids"]) >= MIN_ITEMS_PER_GROUP:
            group_counts[skill_id] += 1
        members = [items[item_id] for item_id in group["item_ids"] if item_id in items]
        if len(members) != len(group["item_ids"]):
            errors.append(f"parallel_groups: {group_id} lists unknown items")
        for field in ("skill_id", "item_type", "response_format", "cognitive_operation"):
            if any(item[field] != group[field] for item in members):
                errors.append(f"parallel_groups: {group_id} items disagree on {field}")
        if len({item["difficulty"] for item in members}) > 1:
            errors.append(f"parallel_groups: {group_id} items have different difficulty")
        if any(item["parallel_group_id"] != group_id for item in members):
            errors.append(f"parallel_groups: {group_id} membership disagrees with items")
        surface = [
            json.dumps(
                [
                    item["parameters"],
                    item["question_text"],
                    item["stimulus"],
                    sorted(
                        (row["text"], json.dumps(row.get("stimulus"), sort_keys=True))
                        for row in item["answer_options"]
                    ),
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
            for item in members
        ]
        if len(set(surface)) != len(surface):
            errors.append(f"parallel_groups: {group_id} has items that differ in no surface value")
    for skill_id in skills:
        if group_counts[skill_id] < MIN_GROUPS_PER_SKILL:
            errors.append(
                f"skills: {skill_id} needs {MIN_GROUPS_PER_SKILL} parallel groups of {MIN_ITEMS_PER_GROUP}+ items"
            )

    for item_id, item in items.items():
        skill_id = item["skill_id"]
        skill = skills.get(skill_id)
        if skill is None:
            errors.append(f"items: {item_id} references unknown skill {skill_id}")
            continue
        if (
            item["parallel_group_id"] not in groups
            or item_id not in groups[item["parallel_group_id"]]["item_ids"]
        ):
            errors.append(f"items: {item_id} is not listed in its parallel group")
        if not SINHALA.search(item["question_text"]):
            errors.append(f"items: {item_id} question_text is not Sinhala")
        rule = templates.get(item["item_type"])
        if rule is None:
            errors.append(f"items: {item_id} item_type {item['item_type']} has no template rule")
        else:
            if not set(item["compatible_templates"]) <= set(rule["compatible_templates"]):
                errors.append(f"items: {item_id} compatible_templates exceed the table entry")
            if item["response_format"] not in rule["response_formats"]:
                errors.append(f"items: {item_id} response format does not suit its item type")
        if item["default_template"] not in item["compatible_templates"]:
            errors.append(f"items: {item_id} default_template is not compatible")
        expected_scaffolds = sorted(
            scaffold_id
            for scaffold_id, scaffold in scaffolds.items()
            if skill_id in scaffold["skill_ids"]
        )
        if sorted(item["available_scaffold_ids"]) != expected_scaffolds:
            errors.append(
                f"items: {item_id} available_scaffold_ids disagree with the skill's scaffolds"
            )
        if item["review_status"] != "draft" and (
            not item["reviewer_id"] or not item["reviewed_on"]
        ):
            errors.append(f"items: {item_id} is not draft but has no reviewer")
        check_reference(
            f"items: {item_id}",
            item["source_reference"],
            set(skill["curriculum_node_ids"]),
            context,
            documents,
            errors,
        )

        options = item["answer_options"]
        option_ids = [row["option_id"] for row in options]
        texts = [row["text"] for row in options]
        if len(set(option_ids)) != len(option_ids) or len(set(texts)) != len(texts):
            errors.append(f"items: {item_id} has duplicate option IDs or texts")
        allowed_codes = skill_codes_by_skill[skill_id] | set(RESERVED_CODES)
        for row in options:
            for code in [row["misconception_code"], *row["alternative_misconception_codes"]]:
                if code is not None and code not in allowed_codes:
                    errors.append(
                        f"items: {item_id} option {row['option_id']} code {code} is not linked to the skill"
                    )
        if item["response_format"] == "binary_sort":
            if item["correct_option_id"] is not None or not item["response_groups"]:
                errors.append(
                    f"items: {item_id} sort items need response groups and no single answer"
                )
            for row in options:
                if row.get("correct_group") is None or row["misconception_code"] is None:
                    errors.append(
                        f"items: {item_id} card {row['option_id']} needs a group and a misplacement code"
                    )
                elif (row["correct_group"] == "yes") != shows_target(
                    row.get("stimulus"), item["parameters"]
                ):
                    errors.append(f"items: {item_id} card {row['option_id']} is in the wrong group")
            if not any(row.get("correct_group") == "yes" for row in options):
                errors.append(f"items: {item_id} has no matching card")
            continue
        correct = [row for row in options if row["option_id"] == item["correct_option_id"]]
        if len(correct) != 1:
            errors.append(f"items: {item_id} correct_option_id does not match one option")
            continue
        if correct[0]["misconception_code"] is not None:
            errors.append(f"items: {item_id} correct option must not carry a misconception code")
        for row in options:
            if row is not correct[0] and row["misconception_code"] is None:
                errors.append(
                    f"items: {item_id} wrong option {row['option_id']} has no misconception or careless/other code"
                )
        if item["parameters"].get("answer_form") == "representation":
            for row in options:
                if shows_target(row.get("stimulus"), item["parameters"]) != (row is correct[0]):
                    errors.append(
                        f"items: {item_id} option {row['option_id']} representation disagrees with the answer"
                    )
        else:
            expected = expected_correct_text(item)
            if expected is None or correct[0]["text"] != expected:
                errors.append(
                    f"items: {item_id} correct option {correct[0]['text']!r} does not equal {expected!r}"
                )

    for scaffold_id, scaffold in scaffolds.items():
        asset = assets.get(scaffold["content_asset_id"])
        if asset is None:
            errors.append(f"scaffolds: {scaffold_id} content asset is missing")
            continue
        if (
            asset["scaffold_type"] != scaffold["scaffold_type"]
            or asset["skill_id"] not in scaffold["skill_ids"]
        ):
            errors.append(f"scaffolds: {scaffold_id} content asset type or skill disagrees")
        if scaffold["approval_status"] != "draft" and (
            not scaffold["reviewer_id"] or not scaffold["reviewed_on"]
        ):
            errors.append(f"scaffolds: {scaffold_id} is not draft but has no reviewer")
        if len(asset["body_si"]) > scaffold["maximum_number_of_steps"]:
            errors.append(f"scaffolds: {scaffold_id} content has more steps than allowed")
        if len(asset["body_si"]) != len(asset["body_en"]):
            errors.append(
                f"content_assets: {asset['content_asset_id']} Sinhala and English steps differ in count"
            )
        if not all(
            SINHALA.search(step) or ARITHMETIC_STEP.fullmatch(step) for step in asset["body_si"]
        ):
            errors.append(f"content_assets: {asset['content_asset_id']} body_si is not Sinhala")
        for skill_id in scaffold["skill_ids"]:
            if skill_id not in skills:
                errors.append(f"scaffolds: {scaffold_id} references unknown skill {skill_id}")
                continue
            for code in scaffold["target_misconception_ids"]:
                if code not in skill_codes_by_skill[skill_id]:
                    errors.append(
                        f"scaffolds: {scaffold_id} targets {code}, which is not linked to {skill_id}"
                    )
            check_reference(
                f"content_assets: {asset['content_asset_id']}",
                asset["source_reference"],
                set(skills[skill_id]["curriculum_node_ids"]),
                context,
                documents,
                errors,
            )
            if "different_values_required" in scaffold["answer_leakage_rules"]:
                scaffold_values = surface_values(asset["parameters"])
                for group in groups.values():
                    if group["skill_id"] != skill_id:
                        continue
                    for item_id in group["item_ids"]:
                        shared = scaffold_values & surface_values(items[item_id]["parameters"])
                        if shared:
                            errors.append(
                                f"scaffolds: {scaffold_id} shares values {sorted(shared)} with {item_id}"
                            )
    for skill_id in skills:
        arms = {
            scaffolds[s]["scaffold_type"]
            for s in scaffolds
            if skill_id in scaffolds[s]["skill_ids"]
        }
        if not set(CANONICAL_ARMS) <= arms:
            errors.append(
                f"skills: {skill_id} is missing scaffold arms {sorted(set(CANONICAL_ARMS) - arms)}"
            )
    return errors


def structured_error_mappings(authored: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    version = VERSIONS["error_mapping_version"]
    rows: list[dict[str, Any]] = []
    for item in authored["items.jsonl"]:
        for option in item["answer_options"]:
            if option["misconception_code"] is None:
                continue
            rows.append(
                {
                    "item_id": item["item_id"],
                    "option_id": option["option_id"],
                    "pattern_code": None,
                    "skill_id": item["skill_id"],
                    "response_format": item["response_format"],
                    "misconception_code": option["misconception_code"],
                    "alternative_misconception_codes": option["alternative_misconception_codes"],
                    "structured_error_code": f"{item['item_id']}:{option['option_id']}",
                    "mapping_version": version,
                    "review_status": item["review_status"],
                }
            )
    for pattern in PATTERN_CODES:
        rows.append(
            {
                "item_id": None,
                "option_id": None,
                "pattern_code": pattern["pattern_code"],
                "skill_id": None,
                "response_format": pattern["response_format"],
                "misconception_code": pattern["misconception_code"],
                "alternative_misconception_codes": [],
                "structured_error_code": pattern["pattern_code"],
                "mapping_version": version,
                "review_status": "draft",
            }
        )
    return rows


def readiness_report(authored: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    skills = [row["skill_code"] for row in authored["skills.jsonl"]]
    reviewable = [
        *(row["status"] for row in authored["skills.jsonl"]),
        *(row["approval_status"] for row in authored["misconception_catalogue.jsonl"]),
        *(row["review_status"] for row in authored["items.jsonl"]),
        *(row["review_status"] for row in authored["parallel_groups.jsonl"]),
        *(row["approval_status"] for row in authored["scaffolds.jsonl"]),
        *(row["approval_status"] for row in authored["content_assets.jsonl"]),
    ]
    approved = sum(status == "approved" for status in reviewable)
    per_skill = {}
    for skill_id in skills:
        groups = [g for g in authored["parallel_groups.jsonl"] if g["skill_id"] == skill_id]
        per_skill[skill_id] = {
            "misconceptions": sum(
                skill_id in row["skill_ids"] and not row["reserved"]
                for row in authored["misconception_catalogue.jsonl"]
            ),
            "items": sum(item["skill_id"] == skill_id for item in authored["items.jsonl"]),
            "parallel_groups": len(groups),
            "items_per_group": sorted(len(g["item_ids"]) for g in groups),
            "scaffold_types": sorted(
                {
                    s["scaffold_type"]
                    for s in authored["scaffolds.jsonl"]
                    if skill_id in s["skill_ids"]
                }
            ),
        }
    pending = "ready_pending_review"
    return {
        "package": PACKAGE,
        "version": PACKAGE_VERSION,
        "scope": "Grade 5 Mathematics Fractions pilot slice (ADR-0006); slice coverage only, not the v2 inventory",
        "gates": {
            "misconception_inference": {
                "status": pending,
                "rule": "3-5 skill misconceptions per skill; every wrong option mapped",
            },
            "support_selection": {
                "status": pending,
                "rule": (
                    "visual_guidance, worked_example and step_by_step_guidance for every skill; "
                    "the authored reference table is a provisional assumption"
                ),
            },
            "independence_gain": {
                "status": pending,
                "rule": f"{MIN_GROUPS_PER_SKILL}+ parallel groups of {MIN_ITEMS_PER_GROUP}+ items per skill",
            },
            "child_facing_delivery": {
                "status": "ready" if approved == len(reviewable) else "blocked_pending_review",
                "rule": "every record approved by a named educator reviewer",
            },
        },
        "review": {"reviewable_records": len(reviewable), "approved_records": approved},
        "skills": per_skill,
    }


def package_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "grade5-pilot-slice-schema-v1",
        "package": PACKAGE,
        "versions": VERSIONS,
        "records": RECORD_SCHEMAS,
    }


def package_readme(authored: Mapping[str, list[dict[str, Any]]]) -> str:
    skills = authored["skills.jsonl"]
    skill_lines = "\n".join(
        f"| `{row['skill_code']}` | {row['labels']['en']} | `{row['universal_skill_id']}` | {row['id_status']} |"
        for row in sorted(skills, key=lambda row: row["stable_index"])
    )
    return f"""# Grade 5 Fractions pilot slice v1

**Researcher-authored draft content awaiting educator review.** Nothing in this package is
approved. Do not show it to children until a named reviewer approves every record; the
`child_facing_delivery` gate in `readiness_report.json` stays blocked until then.

This is the single-unit slice from ADR-0006: Grade 5 Mathematics, Fractions, Sinhala medium.
Skill IDs reuse the v2 candidate IDs, and every skill has the Universal Skill Node parent
`{UNIVERSAL_SKILL_ID}` from `data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl`.
Citations use shared registry source IDs (`data/curriculum/registry/v1/sources.jsonl`) and shared
trace node IDs (`data/curriculum/grade5-curriculum-trace/v1/`). The PDFs those citations refer to
are pinned by SHA-256 in `source_documents.jsonl`; pages are printed page numbers.

| Skill | Description | Universal parent | ID status |
| --- | --- | --- | --- |
{skill_lines}

`G5-MAT-C03-L01-O04` is listed as the first learning outcome in the teacher guide
(SRC-G5-MAT-TG-01 p.31) but has no node in the shared trace. Its ID is appended after the
existing outcomes so no existing ID changes; add the node to the next trace version.

## Files

Authored (edit these): {", ".join(f"`{name}`" for name in AUTHORED_FILES)}.

Generated by `tools/gamification/datasets/build_grade5_pilot_slice.py` (do not edit):
`{GENERATED_JSONL}`, `{REFERENCE_POLICY_JSONL}`, `readiness_report.json`, `schema.json`,
`README.md`, `manifest.json`.

## Review workflow

A reviewer approves a record by setting its status field to `approved` and filling `reviewer_id`
and `reviewed_on`. Approval should not need rewriting: every record is content-complete. Scaffold
time and step limits are provisional assumptions (`limits_status`). Misconceptions marked
`researcher_hypothesis` need teacher confirmation or a literature citation before approval.

Regenerate after any edit:

```sh
python tools/gamification/datasets/build_grade5_pilot_slice.py
python tools/gamification/datasets/build_grade5_pilot_slice.py --check
```
"""


def reference_policy_rows(scaffolds: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Encode the provisional lowest-assistance rule; runtime lookup does not recompute it."""

    by_skill: dict[str, list[dict[str, Any]]] = {}
    for scaffold in scaffolds:
        for skill_id in scaffold["skill_ids"]:
            by_skill.setdefault(str(skill_id), []).append(scaffold)
    rows: list[dict[str, str]] = []
    version = VERSIONS["reference_policy_version"]
    for skill_id, skill_scaffolds in sorted(by_skill.items()):
        codes = sorted(
            {
                code
                for scaffold in skill_scaffolds
                for code in scaffold["target_misconception_ids"]
            }
        )
        for code in codes:
            matching = [
                scaffold
                for scaffold in skill_scaffolds
                if code in scaffold["target_misconception_ids"]
            ]
            chosen = min(
                matching,
                key=lambda scaffold: (
                    scaffold["assistance_level"],
                    len(scaffold["target_misconception_ids"]),
                    scaffold["scaffold_id"],
                ),
            )
            rows.append(
                {
                    "table_version": version,
                    "skill_id": skill_id,
                    "top_misconception_code": code,
                    "preferred_scaffold_type": chosen["scaffold_type"],
                    "authoring_basis": "provisional_assumption",
                    "rule": "lowest_assistance_among_scaffolds_targeting_code",
                }
            )
        lightest = min(
            skill_scaffolds,
            key=lambda scaffold: (
                scaffold["assistance_level"],
                len(scaffold["target_misconception_ids"]),
                scaffold["scaffold_id"],
            ),
        )
        for code in RESERVED_CODES:
            rows.append(
                {
                    "table_version": version,
                    "skill_id": skill_id,
                    "top_misconception_code": code,
                    "preferred_scaffold_type": lightest["scaffold_type"],
                    "authoring_basis": "provisional_assumption",
                    "rule": "least_assistance_scaffold_for_reserved_code",
                }
            )
    return rows


def build_outputs(package_dir: Path, context: Mapping[str, Any]) -> dict[str, str]:
    authored = load_authored(package_dir)
    errors = validate(authored, context)
    mappings = structured_error_mappings(authored)
    policy_rows = reference_policy_rows(authored["scaffolds.jsonl"])
    for index, row in enumerate(mappings):
        errors.extend(
            schema_errors(row, RECORD_SCHEMAS[GENERATED_JSONL], f"{GENERATED_JSONL}[{index}]")
        )
    for index, row in enumerate(policy_rows):
        errors.extend(
            schema_errors(
                row, RECORD_SCHEMAS[REFERENCE_POLICY_JSONL], f"{REFERENCE_POLICY_JSONL}[{index}]"
            )
        )
    if errors:
        raise ValueError(
            "pilot slice validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        )
    outputs = {
        GENERATED_JSONL: render_jsonl(mappings),
        REFERENCE_POLICY_JSONL: render_jsonl(policy_rows),
        "readiness_report.json": render_json(readiness_report(authored)),
        "schema.json": render_json(package_schema()),
        "README.md": package_readme(authored),
    }
    files = {name: (package_dir / name).read_bytes() for name in AUTHORED_FILES} | {
        name: text.encode("utf-8") for name, text in outputs.items()
    }
    sources = {
        str(path.relative_to(PROJECT_ROOT)): {"sha256": sha256_bytes(path.read_bytes())}
        for path in (
            REGISTRY_PATH,
            TRACE_DIR / "manifest.json",
            CROSSWALK_PATH,
            V2_SKILL_CANDIDATES,
            TAXONOMY_WORKBOOK,
        )
    }
    manifest = {
        "package": PACKAGE,
        "version": PACKAGE_VERSION,
        "component_owner": "hareeshagunasekara",
        "review_status": "researcher-authored draft; not reviewed or approved",
        "versions": VERSIONS,
        "counts": {
            name.removesuffix(".jsonl"): len(read_jsonl(package_dir / name))
            for name in AUTHORED_FILES
        }
        | {
            GENERATED_JSONL.removesuffix(".jsonl"): len(mappings),
            REFERENCE_POLICY_JSONL.removesuffix(".jsonl"): len(policy_rows),
        },
        "sources": sources,
        "source_documents": {
            row["source_id"]: {"file_name": row["file_name"], "sha256": row["sha256"]}
            for row in authored["source_documents.jsonl"]
        },
        "files": {
            name: {"bytes": len(data), "sha256": sha256_bytes(data)}
            for name, data in sorted(files.items())
        },
    }
    outputs["manifest.json"] = render_json(manifest)
    return outputs


def verify_source_pdfs(package_dir: Path, raw_dir: Path) -> list[str]:
    problems: list[str] = []
    for row in read_jsonl(package_dir / "source_documents.jsonl"):
        matches = sorted(raw_dir.rglob(row["file_name"]))
        if not matches:
            problems.append(f"{row['source_id']}: {row['file_name']} not found under {raw_dir}")
        elif sha256_bytes(matches[0].read_bytes()) != row["sha256"]:
            problems.append(f"{row['source_id']}: {matches[0]} does not match the pinned SHA-256")
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument(
        "--check", action="store_true", help="Fail if generated files are out of date."
    )
    parser.add_argument(
        "--verify-source-pdfs",
        type=Path,
        nargs="?",
        const=PROJECT_ROOT / "data/curriculum/raw",
        help="Also check the pinned PDF hashes against local PDFs (default data/curriculum/raw).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = build_outputs(args.package_dir, load_context())
    if args.verify_source_pdfs is not None:
        problems = verify_source_pdfs(args.package_dir, args.verify_source_pdfs)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
    if args.check:
        stale = [
            name
            for name, text in outputs.items()
            if not (args.package_dir / name).is_file()
            or (args.package_dir / name).read_text(encoding="utf-8") != text
        ]
        if stale:
            print(f"out of date: {', '.join(stale)}; rerun without --check", file=sys.stderr)
            return 1
        return 0
    for name, text in outputs.items():
        (args.package_dir / name).write_text(text, encoding="utf-8")
    print(json.dumps(json.loads(outputs["manifest.json"])["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
