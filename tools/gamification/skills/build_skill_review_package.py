"""Build the gamification Grade 5 skill catalogue and its Universal Skill Node crosswalk.

The crosswalk (ADR-0010) restores the Phase 5 bindings from a pinned commit, renaming
`knowledge_tracing_skill_id` to `universal_skill_id`, and validates every parent against the
team taxonomy in `docs/skill_nodes.xlsx`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adaptive_tutor.infrastructure.skill_taxonomy import (  # noqa: E402
    XlsxSkillTaxonomyCatalog,
)

GRADE5_DIRECTORY = PROJECT_ROOT / "data" / "gamification" / "grade5-curriculum-game-dataset" / "v2"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "gamification" / "skill-catalogue-review" / "v1"
SOURCE = GRADE5_DIRECTORY / "skill_candidates.jsonl"
TAXONOMY_VERSION = "grade5-gamification-skills-v1"
TAXONOMY_WORKBOOK = PROJECT_ROOT / "docs" / "skill_nodes.xlsx"
CROSSWALK_FILE = "universal-skill-crosswalk.jsonl"
CROSSWALK_VERSION = "grade5-universal-crosswalk-v1"
PHASE5_BINDINGS_COMMIT = "7033835"
PHASE5_BINDINGS_PATH = "data/gamification/skill-catalogue-review/v1/grade5-candidate-skill-bindings.jsonl"
PHASE5_MAPPING_VERSION = "grade5-kt-skill-review-v1"
UNIVERSAL_SKILL_ID_MAX_LENGTH = 16


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def read_phase5_bindings() -> tuple[list[dict[str, object]], str]:
    blob = subprocess.run(
        ["git", "show", f"{PHASE5_BINDINGS_COMMIT}:{PHASE5_BINDINGS_PATH}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines() if line]
    return rows, hashlib.sha256(blob).hexdigest()


def build_crosswalk(
    candidates: list[dict[str, object]],
    phase5_bindings: list[dict[str, object]],
    universal_skill_ids: set[str],
) -> list[dict[str, object]]:
    by_candidate = {str(row["skill_candidate_id"]): row for row in phase5_bindings}
    if len(by_candidate) != len(phase5_bindings):
        raise ValueError("Phase 5 bindings contain duplicate skill candidates")
    candidate_ids = [str(candidate["skill_candidate_id"]) for candidate in candidates]
    if set(candidate_ids) != set(by_candidate):
        raise ValueError("Phase 5 bindings do not cover exactly the current skill candidates")
    crosswalk: list[dict[str, object]] = []
    for skill_id in candidate_ids:
        binding = by_candidate[skill_id]
        universal_skill_id = str(binding["knowledge_tracing_skill_id"])
        if universal_skill_id not in universal_skill_ids:
            raise ValueError(f"{skill_id}: {universal_skill_id} is not in {TAXONOMY_WORKBOOK.name}")
        if len(universal_skill_id) > UNIVERSAL_SKILL_ID_MAX_LENGTH:
            raise ValueError(f"{skill_id}: universal skill ID exceeds the Learner State limit")
        if binding["mapping_version"] != PHASE5_MAPPING_VERSION:
            raise ValueError(f"{skill_id}: unexpected Phase 5 mapping version")
        crosswalk.append({
            "gamification_skill_id": skill_id,
            "universal_skill_id": universal_skill_id,
            "crosswalk_version": CROSSWALK_VERSION,
            "source_mapping_version": PHASE5_MAPPING_VERSION,
            "source_binding_id": binding["binding_id"],
            "confidence": binding["confidence"],
            "rationale": binding["rationale"],
            "source_ids": binding["source_ids"],
            "status": "draft",
            "reviewer_id": None,
            "reviewed_on": None,
        })
    return crosswalk


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    candidates = read_jsonl(SOURCE)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, object]] = []
    reviews: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []

    for stable_index, candidate in enumerate(candidates):
        skill_id = str(candidate["skill_candidate_id"])
        subject = str(candidate["subject"])
        primary = str(candidate.get("label_primary") or skill_id)
        english = str(candidate.get("label_en") or "") or None
        source_id = str(candidate["source_curriculum_node_id"])
        observable = str(candidate.get("observable_success_primary") or primary)
        required_languages = ["en"] if subject == "ENG" else ["si"]
        deferred_languages = [code for code in ("en", "si", "ta") if code not in required_languages]

        inventory.append({
            "skill_code": skill_id,
            "stable_index": stable_index,
            "taxonomy_version": TAXONOMY_VERSION,
            "domain": subject,
            "grade": 5,
            "label_primary": primary,
            "label_en": english,
            "source_curriculum_node_id": source_id,
            "status": "draft",
        })
        reviews.append({
            "skill_code": skill_id,
            "stable_index": stable_index,
            "taxonomy_version": TAXONOMY_VERSION,
            "domain": subject,
            "grade": 5,
            "status": "draft",
            "development_only": True,
            "learner_medium": "si",
            "required_label_languages": required_languages,
            "deferred_languages": deferred_languages,
            "scope_note": "Gamification-owned Grade 5 curriculum skill; review required.",
            "definition": primary,
            "labels": {
                "si": primary if subject != "ENG" else None,
                "en": english or (primary if subject == "ENG" else None),
                "ta": None,
            },
            "prerequisites": list(candidate.get("prerequisite_skill_candidate_ids") or []),
            "observable_success": [observable],
            "misconceptions": list(candidate.get("misconception_codes") or ["unknown/other"]),
            "distinguishing_evidence": [observable],
            "eligible_support_action_types": list(candidate.get("eligible_support_action_types") or []),
            "verification_pair_rules": {"same_skill": True, "unseen_item": True},
            "source_citations": [{
                "source_id": source_id,
                "page_from": "curriculum-node",
                "page_to": "curriculum-node",
                "skill_candidate_ids": [skill_id],
            }],
            "reviewer_id": None,
            "reviewed_on": None,
            "superseded_by": None,
        })
        bindings.append({
            "skill_candidate_id": skill_id,
            "gamification_skill_id": skill_id,
            "mapping_version": TAXONOMY_VERSION,
            "status": "draft",
            "confidence": "high",
            "rationale": "Identity binding within the gamification-owned skill catalogue.",
            "source_ids": [source_id],
            "reviewer_id": None,
            "reviewed_on": None,
        })

    phase5_bindings, phase5_sha256 = read_phase5_bindings()
    universal_skill_ids = {node.skill_id for node in XlsxSkillTaxonomyCatalog(TAXONOMY_WORKBOOK).load()}
    crosswalk = build_crosswalk(candidates, phase5_bindings, universal_skill_ids)

    generated = {
        "skill-inventory.jsonl": inventory,
        "development-skill-reviews.jsonl": reviews,
        "grade5-candidate-skill-bindings.jsonl": bindings,
        CROSSWALK_FILE: crosswalk,
    }
    for name, records in generated.items():
        write_jsonl(OUTPUT_DIRECTORY / name, records)

    schema = {
        "schema_version": "gamification-skill-catalogue-v1",
        "taxonomy_version": TAXONOMY_VERSION,
        "ownership": "gamification",
        "binding_key": "gamification_skill_id",
        "crosswalk_key": "universal_skill_id",
        "crosswalk_version": CROSSWALK_VERSION,
    }
    (OUTPUT_DIRECTORY / "schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    files = (*generated, "schema.json")
    manifest = {
        "package": "gamification-skill-catalogue",
        "component_owner": "hareeshagunasekara",
        "version": "1.0.0",
        "taxonomy_version": TAXONOMY_VERSION,
        "ownership": "gamification",
        "counts": {
            "skills": len(inventory),
            "bindings": len(bindings),
            "crosswalk_rows": len(crosswalk),
            "approved": 0,
        },
        "sources": {
            str(SOURCE.relative_to(PROJECT_ROOT)): {"sha256": digest(SOURCE)},
            str(TAXONOMY_WORKBOOK.relative_to(PROJECT_ROOT)): {"sha256": digest(TAXONOMY_WORKBOOK)},
            f"git:{PHASE5_BINDINGS_COMMIT}:{PHASE5_BINDINGS_PATH}": {"sha256": phase5_sha256},
        },
        "files": {
            name: {"bytes": (OUTPUT_DIRECTORY / name).stat().st_size, "sha256": digest(OUTPUT_DIRECTORY / name)}
            for name in files
        },
        "gates": {"development": "pass", "child_facing": "blocked_pending_review"},
    }
    (OUTPUT_DIRECTORY / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
