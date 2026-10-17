"""Validate and deterministically manifest the one-skill Sinhala curriculum package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.gamification.content.curriculum_registry import (
    CURRICULUM_CONTENT_DIRECTORY,
    CURRICULUM_PACKAGE_VERSION,
    PublicCurriculumPackage,
    load_curriculum_server_answer_keys,
)

AUTHORED_FILES = ("README.md", "public_content.json", "server_answer_keys.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(path: Path) -> str:
    package = PublicCurriculumPackage.model_validate_json(
        (path / "public_content.json").read_text(encoding="utf-8")
    )
    answer_rows = json.loads((path / "server_answer_keys.json").read_text(encoding="utf-8"))
    revision_ids = {row["revision_id"] for row in answer_rows}
    if revision_ids != {item.revision_id for item in package.item_revisions}:
        raise ValueError("answer keys must exactly cover the immutable item revisions")
    manifest = {
        "package_version": CURRICULUM_PACKAGE_VERSION,
        "scope": "one_atomic_grade5_sinhala_skill",
        "skill_id": package.skill.skill_id,
        "child_delivery_status": (
            "approved" if package.approved_for_child_delivery() else "blocked_pending_human_review"
        ),
        "files": {
            name: _sha256((path / name).read_bytes()) for name in sorted(AUTHORED_FILES)
        },
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def verify_source(path: Path) -> None:
    package = PublicCurriculumPackage.model_validate_json(
        (path / "public_content.json").read_text(encoding="utf-8")
    )
    source_path = PROJECT_ROOT / package.source.source_path
    if not source_path.is_file():
        raise ValueError(f"source file not found: {source_path}")
    if _sha256(source_path.read_bytes()) != package.source.source_sha256:
        raise ValueError("source PDF hash does not match the pinned source")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=CURRICULUM_CONTENT_DIRECTORY)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-source", action="store_true")
    args = parser.parse_args()
    rendered = build_manifest(args.package_dir)
    if args.verify_source:
        verify_source(args.package_dir)
    manifest_path = args.package_dir / "manifest.json"
    if args.check:
        if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != rendered:
            raise SystemExit("content manifest is out of date")
        # Full loader verification includes manifest integrity and server/public key consistency.
        load_curriculum_server_answer_keys(args.package_dir)
        return 0
    manifest_path.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
