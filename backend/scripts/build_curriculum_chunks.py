"""Write chunking-v1 files from the shared trace, registry, and extracted page text.

Rows stay REVIEW_PENDING. A local PDF hash is recorded in the manifest and does not mark
the source INGESTED. Gamification item files are not inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.curriculum.application.chunking import (
    QuarantineRecord,
    apply_universal_skill_links,
    build_manifest,
    chunk_curriculum,
    load_chunk_sources,
    load_extracted_pages,
    load_trace_nodes,
    load_universal_skill_links,
    read_curriculum_jsonl,
    refuse_non_curriculum_path,
    render_jsonl,
)

DEFAULT_NODES = (
    REPOSITORY_ROOT / "data/curriculum/grade5-curriculum-trace/v1/curriculum_nodes.jsonl"
)
DEFAULT_REGISTRY = REPOSITORY_ROOT / "data/curriculum/registry/v1/sources.jsonl"
DEFAULT_EXTRACTED = REPOSITORY_ROOT / "data/curriculum/extracted"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data/curriculum/chunks/v1"
DEFAULT_SKILL_LINKS = (
    REPOSITORY_ROOT / "data/curriculum/skill-links/v1/outcome-universal-skills.jsonl"
)
RAW_MARKER = "data/curriculum/raw/"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_raw_path(source_location: str) -> str | None:
    marker = source_location.find(RAW_MARKER)
    if marker < 0:
        return None
    return source_location[marker + len(RAW_MARKER) :]


def placed_document_hashes(registry_path: Path) -> tuple[dict[str, str | None], dict[str, str]]:
    """Hash each placed PDF. Missing files stay unpinned and NOT_INGESTED."""

    hashes: dict[str, str | None] = {}
    locations: dict[str, str] = {}
    for row in read_curriculum_jsonl(registry_path):
        source_id = str(row["source_id"])
        location = row.get("source_location")
        relative = relative_raw_path(str(location)) if isinstance(location, str) else None
        if relative is None:
            hashes[source_id] = None
            continue
        locations[relative] = source_id
        pdf_path = REPOSITORY_ROOT / "data/curriculum/raw" / relative
        refuse_non_curriculum_path(pdf_path)
        hashes[source_id] = hash_file(pdf_path) if pdf_path.is_file() else None
    return hashes, locations


def write_outputs(
    output_dir: Path,
    *,
    nodes_path: Path,
    registry_path: Path,
    extracted_root: Path,
    skill_links_path: Path | None = None,
) -> dict[str, object]:
    for path in (output_dir, nodes_path, registry_path, extracted_root):
        refuse_non_curriculum_path(path)
    document_hashes, locations = placed_document_hashes(registry_path)
    nodes = load_trace_nodes(nodes_path)
    if skill_links_path is not None:
        nodes = apply_universal_skill_links(nodes, load_universal_skill_links(skill_links_path))
    sources = load_chunk_sources(registry_path, document_sha256=document_hashes)
    pages = load_extracted_pages(extracted_root, locations)
    result = chunk_curriculum(nodes, sources, pages)
    extracted_source_ids = {page.source_id for page in pages}
    quarantine = list(result.quarantine)
    for source_id, digest in sorted(document_hashes.items()):
        if digest and source_id not in extracted_source_ids:
            quarantine.append(QuarantineRecord(reason="extraction_missing", source_id=source_id))
    quarantine_rows = tuple(sorted(quarantine, key=lambda row: (row.reason, row.source_id or "")))
    chunks_text = render_jsonl(result.chunks)
    quarantine_text = render_jsonl(quarantine_rows)
    reason_counts = Counter(row.reason for row in quarantine_rows)
    manifest = build_manifest(
        chunks_text=chunks_text,
        quarantine_text=quarantine_text,
        written_count=len(result.chunks),
        quarantined_count=len(quarantine_rows),
        reason_counts=reason_counts,
        source_document_sha256=document_hashes,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "chunks.jsonl").write_text(chunks_text, encoding="utf-8")
    (output_dir / "quarantine.jsonl").write_text(quarantine_text, encoding="utf-8")
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build shared curriculum chunks, version chunking-v1."
    )
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--extracted", type=Path, default=DEFAULT_EXTRACTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skill-links", type=Path, default=DEFAULT_SKILL_LINKS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = write_outputs(
        args.output,
        nodes_path=args.nodes,
        registry_path=args.registry,
        extracted_root=args.extracted,
        skill_links_path=args.skill_links if args.skill_links.is_file() else None,
    )
    print(
        f"chunking-v1 wrote {manifest['written_count']} chunks and "
        f"quarantined {manifest['quarantined_count']} rows. "
        "Every written row is REVIEW_PENDING. No source was marked INGESTED."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
