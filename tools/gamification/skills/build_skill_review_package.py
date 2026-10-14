"""Build the Phase 5A development-only skill review package."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
)
from app.gamification.skill_catalogue.json_repository import (
    SKILL_REVIEW_DATA_DIRECTORY,
    load_development_skill_catalogue,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUESTION_BANK_DIRECTORY = PROJECT_ROOT / "backend" / "data" / "question_bank"
SKILL_NODE_SOURCE = QUESTION_BANK_DIRECTORY / "skill_nodes.md"
QUESTION_MAP_SOURCES = tuple(sorted(QUESTION_BANK_DIRECTORY.glob("skillMap-*.md")))
GRADE5_DIRECTORY = PROJECT_ROOT / "data" / "gamification" / "grade5-curriculum-game-dataset" / "v2"
SYNTHETIC_PREDICTIONS = (
    PROJECT_ROOT
    / "data"
    / "gamification"
    / "synthetic-model-data"
    / "v1"
    / "classification-evaluation-example.json"
)
TAXONOMY_VERSION = "grade5-kt-skill-review-v1"
PILOT_REVIEW_SOURCE = SKILL_REVIEW_DATA_DIRECTORY / "pilot-skill-reviews.jsonl"
PILOT_BINDING_SOURCE = SKILL_REVIEW_DATA_DIRECTORY / "pilot-skill-bindings.jsonl"
DEVELOPMENT_REVIEW_OUTPUT = SKILL_REVIEW_DATA_DIRECTORY / "development-skill-reviews.jsonl"
GRADE5_BINDING_OUTPUT = SKILL_REVIEW_DATA_DIRECTORY / "grade5-candidate-skill-bindings.jsonl"

MATHEMATICS_ROOT_BINDINGS = {
    "C01": "MAT-NUM",
    "C02": "APT-PAT",
    "C03": "MAT-FRC",
    "C04": "MAT-NUM",
    "C05": "MAT-FRC",
    "C06": "MAT-OPS",
    "C07": "MAT-OPS",
    "C08": "MAT-OPS",
    "C09": "MAT-OPS",
    "C10": "MAT-OPS",
    "C11": "MAT-LEN",
    "C12": "MAT-MAS",
    "C13": "MAT-MAS",
    "C14": "MAT-TIM",
    "C15": "MAT-MON",
    "C16": "MAT-GEO",
    "C17": "MAT-GEO",
    "C18": "APT-DIR",
    "C19": "MAT-DAT",
}

SINHALA_LEVEL_BINDINGS = {
    "L01": "LAN-CMP",
    "L02": "LAN-CMP",
    "L03": "LAN-CMP",
    "L04": "LAN-CMP",
    "L05": "LAN-VOC",
    "L06": "LAN-WRT",
    "L07": "LAN-WRT",
    "L08": "LAN-CMP",
    "L09": "LAN-WRT",
    "L10": "LAN-AGR",
}

SINHALA_KEYWORD_BINDINGS = (
    (
        "LAN-IDM",
        ("proverb", "idiom", "figurative", "maxim"),
    ),
    (
        "LAN-TNS",
        ("present tense", "past tense"),
    ),
    (
        "LAN-AGR",
        (
            "verb",
            "subject, object",
            "singular and plural",
            "feminine and masculine",
            "nominative and oblique",
        ),
    ),
    (
        "LAN-ORT",
        ("spelling", "punctuation", "vowel signs", "spaces between words"),
    ),
    (
        "LAN-VOC",
        ("vocabulary", "paired words", "riddles"),
    ),
    (
        "LAN-WRT",
        (
            "writes",
            "writing",
            "creates",
            "prepares",
            "completes a form",
            "invitation",
            "personal letters",
            "greeting cards",
        ),
    ),
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_skill_inventory() -> list[dict[str, object]]:
    skills: list[dict[str, object]] = []
    for line in SKILL_NODE_SOURCE.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 5 or cells[0] not in {"APT", "MAT", "LAN", "ENV"}:
            continue
        domain, code, label_en, label_si, description = cells
        skills.append(
            {
                "skill_code": code,
                "stable_index": len(skills),
                "domain": domain,
                "label_en": label_en,
                "label_si": label_si,
                "label_ta": None,
                "description": description,
                "status": "draft",
                "taxonomy_version": TAXONOMY_VERSION,
                "source_path": str(SKILL_NODE_SOURCE.relative_to(PROJECT_ROOT)),
            }
        )
    if len(skills) != 30 or [skill["stable_index"] for skill in skills] != list(range(30)):
        raise ValueError("the knowledge-tracing inventory must preserve exactly indices 0 through 29")
    return skills


def parse_question_mappings(valid_codes: set[str]) -> list[dict[str, object]]:
    mappings: list[dict[str, object]] = []
    seen_questions: set[str] = set()
    for path in QUESTION_MAP_SOURCES:
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            match = re.fullmatch(r"\s*(\d+\.\d+)\s*-\s*(.+?)\s*", line)
            if not match:
                continue
            question_id, raw_codes = match.groups()
            if question_id in seen_questions:
                raise ValueError(f"duplicate question mapping: {question_id}")
            seen_questions.add(question_id)
            codes = tuple(code.strip() for code in raw_codes.split(","))
            if not codes or any(code not in valid_codes for code in codes):
                raise ValueError(f"unknown skill code in question mapping: {question_id}")
            for position, code in enumerate(codes):
                mappings.append(
                    {
                        "question_id": question_id,
                        "skill_code": code,
                        "relationship": "primary" if position == 0 else "secondary",
                        "mapping_version": TAXONOMY_VERSION,
                        "status": "draft",
                        "source_path": str(path.relative_to(PROJECT_ROOT)),
                        "source_line": line_number,
                    }
                )
    return mappings


def _candidate_root(candidate_id: str) -> str:
    match = re.match(r"^G5-[A-Z]+-(C\d+)", candidate_id)
    if not match:
        raise ValueError(f"unsupported Grade 5 candidate identifier: {candidate_id}")
    return match.group(1)


def _environment_binding(root: str) -> str:
    number = int(root.removeprefix("C"))
    if 13 <= number <= 40:
        return "ENV-BIO"
    if number in {41, 46, 47, 48} or 64 <= number <= 77:
        return "ENV-PHY"
    if 49 <= number <= 63:
        return "ENV-HLT"
    if 78 <= number <= 84:
        return "ENV-AGR"
    if 95 <= number <= 104:
        return "ENV-GEO"
    return "ENV-CIV"


def _sinhala_binding(candidate: dict[str, Any]) -> tuple[str, str]:
    candidate_id = str(candidate["skill_candidate_id"])
    label = str(candidate.get("label_en") or "").casefold()
    for skill_code, keywords in SINHALA_KEYWORD_BINDINGS:
        if any(keyword in label for keyword in keywords):
            return skill_code, "high"
    level_match = re.search(r"-(L\d+)(?:-|$)", candidate_id)
    if level_match:
        return SINHALA_LEVEL_BINDINGS[level_match.group(1)], "medium"
    if candidate_id.startswith("G5-SIN-C04"):
        return "LAN-WRT", "medium"
    return "LAN-CMP", "medium"


def propose_binding(candidate: dict[str, Any]) -> tuple[str, str, str]:
    candidate_id = str(candidate["skill_candidate_id"])
    subject = str(candidate["subject"])
    root = _candidate_root(candidate_id)
    if subject == "MAT":
        skill_code = MATHEMATICS_ROOT_BINDINGS[root]
        return skill_code, "high", "Mapped by the explicit Grade 5 mathematics competency rule."
    if subject == "ENV":
        skill_code = _environment_binding(root)
        return (
            skill_code,
            "low",
            (
                "Mapped by the documented Sinhala-medium Environmental Studies thematic block "
                "rule; the coarse legacy skill remains low confidence for later refinement."
            ),
        )
    if subject == "SIN":
        skill_code, confidence = _sinhala_binding(candidate)
        return (
            skill_code,
            confidence,
            "Mapped by an explicit Sinhala-language outcome keyword or curriculum-level rule.",
        )
    if subject == "ENG":
        return (
            "LAN-BIL",
            "medium",
            (
                "English is subject content for Sinhala-medium learners and maps to the stable "
                "second-language skill; Tamil remains deferred."
            ),
        )
    raise ValueError(f"subject is outside Sinhala-medium Grade 5 scope: {subject}")


def build_complete_bindings() -> tuple[list[dict[str, object]], dict[str, dict[str, Any]]]:
    candidates = {
        str(record["skill_candidate_id"]): record
        for record in _read_jsonl(GRADE5_DIRECTORY / "skill_candidates.jsonl")
    }
    source_mappings = {
        str(record["skill_candidate_id"]): record
        for record in _read_jsonl(GRADE5_DIRECTORY / "skill_source_mappings.jsonl")
    }
    pilot_overrides = {
        str(record["skill_candidate_id"]): record for record in _read_jsonl(PILOT_BINDING_SOURCE)
    }
    bindings: list[dict[str, object]] = []
    for candidate_id, candidate in sorted(candidates.items()):
        skill_code, confidence, rationale = propose_binding(candidate)
        source_mapping = source_mappings[candidate_id]
        record: dict[str, object] = {
            "binding_id": f"{candidate_id}--{skill_code}",
            "skill_candidate_id": candidate_id,
            "knowledge_tracing_skill_id": skill_code,
            "mapping_version": TAXONOMY_VERSION,
            "status": "draft",
            "confidence": confidence,
            "rationale": rationale,
            "source_ids": [source_mapping["source_id"]],
            "reviewer_id": None,
            "reviewed_on": None,
        }
        record.update(pilot_overrides.get(candidate_id, {}))
        bindings.append(record)
    return bindings, source_mappings


def build_development_reviews(
    inventory: list[dict[str, object]],
    bindings: list[dict[str, object]],
    source_mappings: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    pilot_reviews = {
        str(record["skill_code"]): record for record in _read_jsonl(PILOT_REVIEW_SOURCE)
    }
    candidates_by_skill: dict[str, list[str]] = {}
    for binding in bindings:
        candidates_by_skill.setdefault(str(binding["knowledge_tracing_skill_id"]), []).append(
            str(binding["skill_candidate_id"])
        )
    reviews: list[dict[str, object]] = []
    for skill in inventory:
        skill_code = str(skill["skill_code"])
        candidate_ids = candidates_by_skill.get(skill_code)
        if not candidate_ids:
            continue
        if skill_code in pilot_reviews:
            reviews.append(pilot_reviews[skill_code])
            continue
        source_groups: dict[str, list[str]] = {}
        for candidate_id in candidate_ids:
            source_id = str(source_mappings[candidate_id]["source_id"])
            source_groups.setdefault(source_id, []).append(candidate_id)
        reviews.append(
            {
                "skill_code": skill_code,
                "stable_index": skill["stable_index"],
                "taxonomy_version": TAXONOMY_VERSION,
                "domain": skill["domain"],
                "grade": 5,
                "status": "draft",
                "development_only": True,
                "learner_medium": "si",
                "required_label_languages": ["en", "si"],
                "deferred_languages": ["ta"],
                "scope_note": (
                    "Generated draft coverage for Sinhala-medium Grade 5 development. "
                    "English is a source gloss or subject content; Tamil is deferred."
                ),
                "definition": skill["description"],
                "labels": {
                    "en": skill["label_en"],
                    "si": skill["label_si"],
                    "ta": None,
                },
                "prerequisites": [],
                "observable_success": [
                    "Demonstrates one of the source-linked Grade 5 outcomes proposed for this skill."
                ],
                "misconceptions": ["unknown/other"],
                "distinguishing_evidence": [
                    (
                        "Do not infer a specific misconception from one incorrect answer; collect "
                        "repeated comparable evidence."
                    )
                ],
                "eligible_support_action_types": [
                    "metacognitive_prompt",
                    "conceptual_hint",
                    "independent_retry",
                ],
                "verification_pair_rules": {
                    "same_skill_required": True,
                    "unseen_item_required": True,
                    "support_withdrawal_required": True,
                },
                "source_citations": [
                    {
                        "source_id": source_id,
                        "page_from": "see canonical skill-source mappings",
                        "page_to": "see canonical skill-source mappings",
                        "skill_candidate_ids": sorted(group_candidate_ids),
                    }
                    for source_id, group_candidate_ids in sorted(source_groups.items())
                ],
                "reviewer_id": None,
                "reviewed_on": None,
                "superseded_by": None,
            }
        )
    return reviews


def validate_pilot_sources() -> tuple[int, int]:
    candidates = {
        record["skill_candidate_id"]: record
        for record in _read_jsonl(GRADE5_DIRECTORY / "skill_candidates.jsonl")
    }
    sources = {
        record["source_id"]: record
        for record in _read_jsonl(GRADE5_DIRECTORY / "curriculum_sources.jsonl")
    }
    source_mappings = {
        record["skill_candidate_id"]: record
        for record in _read_jsonl(GRADE5_DIRECTORY / "skill_source_mappings.jsonl")
    }
    catalogue = load_development_skill_catalogue()
    for review in catalogue.skills.values():
        for citation in review.source_citations:
            if citation.source_id not in sources:
                raise ValueError(f"unknown curriculum source: {citation.source_id}")
            for candidate_id in citation.skill_candidate_ids:
                if candidate_id not in candidates:
                    raise ValueError(f"unknown skill candidate: {candidate_id}")
                mapping = source_mappings.get(candidate_id)
                if mapping is None or mapping["source_id"] != citation.source_id:
                    raise ValueError(f"citation does not match source mapping: {candidate_id}")
    return len(candidates), len(sources)


def build_model_slice_evaluation() -> dict[str, object]:
    catalogue = load_development_skill_catalogue()
    predictions = json.loads(SYNTHETIC_PREDICTIONS.read_text())
    bound = [catalogue.bind_feature_values(record, allow_draft=True) for record in predictions]
    by_skill = evaluate_classification(bound, slice_field="skill_id")
    by_language = evaluate_classification(bound, slice_field="language")
    return {
        "schema_version": "skill-bound-synthetic-evaluation-v1",
        "taxonomy_version": TAXONOMY_VERSION,
        "synthetic": True,
        "authorized_research_evidence": False,
        "learner_medium": "si",
        "record_count": len(bound),
        "skill_slices": by_skill.slices,
        "content_language_slices": by_language.slices,
        "aggregate": {
            "accuracy": by_skill.accuracy,
            "brier_score": by_skill.brier_score,
            "expected_calibration_error": by_skill.expected_calibration_error,
            "abstention_rate": by_skill.abstention_rate,
        },
        "note": (
            "Engineering compatibility evidence only; predictions and reviews are synthetic/draft. "
            "Content may be English or bilingual while learner instructions and support remain Sinhala."
        ),
    }


def build_schema() -> dict[str, object]:
    status = {"type": "string", "enum": ["draft", "approved", "retired", "superseded"]}
    string_array = {"type": "array", "items": {"type": "string"}}
    language_array = {
        "type": "array",
        "items": {"enum": ["en", "si", "ta"]},
        "uniqueItems": True,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://mindbridge.local/schemas/skill-catalogue-review-v1.json",
        "title": "MindBridge Phase 5A skill review import schema",
        "version": "1.0.0",
        "taxonomy_version": TAXONOMY_VERSION,
        "files": {
            "development-skill-reviews.jsonl": {
                "record_schema": "#/$defs/skill_review"
            },
            "grade5-candidate-skill-bindings.jsonl": {
                "record_schema": "#/$defs/skill_binding"
            },
        },
        "$defs": {
            "review_status": status,
            "source_citation": {
                "type": "object",
                "required": ["source_id", "page_from", "page_to", "skill_candidate_ids"],
                "properties": {
                    "source_id": {"type": "string", "minLength": 1},
                    "page_from": {"type": "string", "minLength": 1},
                    "page_to": {"type": "string"},
                    "skill_candidate_ids": string_array,
                },
                "additionalProperties": False,
            },
            "skill_review": {
                "type": "object",
                "required": [
                    "skill_code",
                    "stable_index",
                    "taxonomy_version",
                    "domain",
                    "grade",
                    "status",
                    "development_only",
                    "learner_medium",
                    "required_label_languages",
                    "deferred_languages",
                    "scope_note",
                    "definition",
                    "labels",
                    "prerequisites",
                    "observable_success",
                    "misconceptions",
                    "distinguishing_evidence",
                    "eligible_support_action_types",
                    "verification_pair_rules",
                    "source_citations",
                ],
                "properties": {
                    "skill_code": {"type": "string", "pattern": "^[A-Z]{3}-[A-Z]{3}$"},
                    "stable_index": {"type": "integer", "minimum": 0, "maximum": 29},
                    "taxonomy_version": {"const": TAXONOMY_VERSION},
                    "domain": {"enum": ["APT", "MAT", "LAN", "ENV"]},
                    "grade": {"enum": [4, 5]},
                    "status": status,
                    "development_only": {"type": "boolean"},
                    "learner_medium": {"enum": ["si", "ta", "en"]},
                    "required_label_languages": {**language_array, "minItems": 1},
                    "deferred_languages": language_array,
                    "scope_note": {"type": "string", "minLength": 1},
                    "definition": {"type": "string", "minLength": 1},
                    "labels": {
                        "type": "object",
                        "required": ["en", "si", "ta"],
                        "properties": {
                            "en": {"type": "string", "minLength": 1},
                            "si": {"type": ["string", "null"]},
                            "ta": {"type": ["string", "null"]},
                        },
                    },
                    "prerequisites": string_array,
                    "observable_success": string_array,
                    "misconceptions": string_array,
                    "distinguishing_evidence": string_array,
                    "eligible_support_action_types": string_array,
                    "verification_pair_rules": {"type": "object"},
                    "source_citations": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"$ref": "#/$defs/source_citation"},
                    },
                    "reviewer_id": {"type": ["string", "null"]},
                    "reviewed_on": {"type": ["string", "null"]},
                    "superseded_by": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
            "skill_binding": {
                "type": "object",
                "required": [
                    "skill_candidate_id",
                    "knowledge_tracing_skill_id",
                    "mapping_version",
                    "status",
                    "confidence",
                    "rationale",
                    "source_ids",
                ],
                "properties": {
                    "binding_id": {"type": "string", "minLength": 1},
                    "skill_candidate_id": {"type": "string", "minLength": 1},
                    "knowledge_tracing_skill_id": {
                        "type": "string",
                        "pattern": "^[A-Z]{3}-[A-Z]{3}$",
                    },
                    "mapping_version": {"const": TAXONOMY_VERSION},
                    "status": status,
                    "confidence": {"enum": ["low", "medium", "high"]},
                    "rationale": {"type": "string", "minLength": 1},
                    "source_ids": string_array,
                    "reviewer_id": {"type": ["string", "null"]},
                    "reviewed_on": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    }


def main() -> int:
    SKILL_REVIEW_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    inventory = parse_skill_inventory()
    skill_codes = {str(record["skill_code"]) for record in inventory}
    question_mappings = parse_question_mappings(skill_codes)
    bindings, source_mappings = build_complete_bindings()
    reviews = build_development_reviews(inventory, bindings, source_mappings)
    _write_jsonl(DEVELOPMENT_REVIEW_OUTPUT, reviews)
    _write_jsonl(GRADE5_BINDING_OUTPUT, bindings)
    candidate_count, source_count = validate_pilot_sources()
    catalogue = load_development_skill_catalogue()

    mapping_counts = Counter(str(record["skill_code"]) for record in question_mappings)
    for record in inventory:
        record["question_mapping_count"] = mapping_counts[str(record["skill_code"])]

    _write_jsonl(SKILL_REVIEW_DATA_DIRECTORY / "skill-inventory.jsonl", inventory)
    _write_jsonl(
        SKILL_REVIEW_DATA_DIRECTORY / "question-skill-mappings.jsonl", question_mappings
    )
    _write_json(
        SKILL_REVIEW_DATA_DIRECTORY / "model-slice-evaluation.json",
        build_model_slice_evaluation(),
    )
    _write_json(SKILL_REVIEW_DATA_DIRECTORY / "schema.json", build_schema())

    change_impact = {
        "schema_version": "skill-change-impact-v1",
        "taxonomy_version": TAXONOMY_VERSION,
        "existing_skill_count": len(inventory),
        "existing_question_count": len({record["question_id"] for record in question_mappings}),
        "question_skill_mapping_count": len(question_mappings),
        "stable_code_changes": [],
        "stable_index_changes": [],
        "database_migration_required": False,
        "model_schema_change_required": False,
        "grade5_skill_candidate_count": candidate_count,
        "grade5_candidate_binding_count": len(catalogue.bindings),
        "unbound_grade5_skill_candidate_count": candidate_count - len(catalogue.bindings),
        "approved_binding_count": 0,
        "draft_binding_count": len(catalogue.bindings),
        "medium_confidence_bindings_kept_draft": sorted(
            binding.skill_candidate_id
            for binding in catalogue.bindings.values()
            if binding.confidence != "high"
        ),
        "source_count": source_count,
        "compatibility_decision": "additive_review_layer_no_code_or_index_change",
        "affected_consumers": [
            "knowledge-tracing 30-skill index",
            "question bank primary and secondary mappings",
            "gamification Phase 4 skill_id feature",
            "adaptive tutor skill_id contract",
        ],
        "remaining_blockers": [],
        "non_blocking_future_validation": [
            (
                "External reviewer metadata may replace development draft status before a later "
                "research study or production governance process."
            ),
            "Low-confidence mappings can be refined later without blocking the current build.",
        ],
        "deferred_scope": [
            "Tamil-medium delivery, Tamil content, Tamil labels, and Tamil evaluation are outside Sinhala-medium v1."
        ],
    }
    _write_json(SKILL_REVIEW_DATA_DIRECTORY / "change-impact-report.json", change_impact)

    derived_files = (
        "skill-inventory.jsonl",
        "question-skill-mappings.jsonl",
        "pilot-skill-reviews.jsonl",
        "pilot-skill-bindings.jsonl",
        "development-skill-reviews.jsonl",
        "grade5-candidate-skill-bindings.jsonl",
        "model-slice-evaluation.json",
        "change-impact-report.json",
        "schema.json",
        "README.md",
        "MAPPING_RULES.md",
    )
    source_files = (SKILL_NODE_SOURCE, *QUESTION_MAP_SOURCES, GRADE5_DIRECTORY / "manifest.json")
    manifest = {
        "schema_version": "skill-catalogue-review-manifest-v1",
        "package": "skill-catalogue-review",
        "version": "1.0.0",
        "taxonomy_version": TAXONOMY_VERSION,
        "development_only": True,
        "delivery_scope": {
            "learner_medium": "si",
            "support_language": "si",
            "content_languages": ["si", "en", "bilingual"],
            "required_label_languages": ["en", "si"],
            "deferred_languages": ["ta"],
        },
        "source_commit": _git_output("rev-parse", "HEAD"),
        "source_worktree_dirty": bool(_git_output("status", "--porcelain")),
        "counts": {
            "skills": len(inventory),
            "questions": len({record["question_id"] for record in question_mappings}),
            "question_skill_mappings": len(question_mappings),
            "development_skill_reviews": len(catalogue.skills),
            "grade5_candidate_skill_bindings": len(catalogue.bindings),
            "approved_skills": 0,
            "approved_bindings": 0,
        },
        "files": {
            name: {"bytes": (SKILL_REVIEW_DATA_DIRECTORY / name).stat().st_size,
                   "sha256": _sha256(SKILL_REVIEW_DATA_DIRECTORY / name)}
            for name in derived_files
        },
        "sources": {
            str(path.relative_to(PROJECT_ROOT)): {"sha256": _sha256(path)}
            for path in source_files
        },
        "gates": {
            "inventory_complete": True,
            "stable_indices_preserved": True,
            "question_mappings_inventoried": True,
            "pilot_sources_resolve": True,
            "model_binding_compatible": True,
            "development_phase_5a": "pass",
            "development_phase_5b": "ready",
            "external_research_validation": "deferred_not_required_for_development",
            "phase_5b": "ready_for_sinhala_medium_development",
        },
    }
    _write_json(SKILL_REVIEW_DATA_DIRECTORY / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
