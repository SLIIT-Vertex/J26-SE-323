"""Build the shared curriculum source registry from the Grade 5 curriculum trace.

Every record is written as provisional, not ingested, unreviewed, and with unknown usage rights.
The trace records which authority a document names; that is kept as the stated publisher, but it
is not treated as verified metadata, approval, or permission to use the content.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.curriculum.application.retrieval import (
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    UsageRightsStatus,
)

DEFAULT_TRACE_SOURCES = (
    REPOSITORY_ROOT / "data/curriculum/grade5-curriculum-trace/v1/curriculum_sources.jsonl"
)
DEFAULT_REGISTRY = REPOSITORY_ROOT / "data/curriculum/registry/v1/sources.jsonl"
RAW_SOURCE_DIRECTORY = "data/curriculum/raw"
SUBJECT_NAMES = {
    "ENV": "Environmental Studies",
    "SIN": "Sinhala",
    "ENG": "English",
    "MAT": "Mathematics",
}
RAW_SUBJECT_DIRECTORIES = {
    "ENV": "environmental-studies",
    "SIN": "sinhala",
    "ENG": "english",
    "MAT": "mathematics",
}
LANGUAGE_CODES = {"Sinhala": "si", "English": "en"}


def _text(row: Mapping[str, Any], field: str) -> str | None:
    value = str(row.get(field) or "").strip()
    return value or None


def registry_record(row: Mapping[str, Any]) -> CurriculumSourceRecord:
    subject_code = str(row["subject"])
    language = str(row["language"])
    if subject_code not in SUBJECT_NAMES:
        raise ValueError(f"{row['source_id']}: unknown subject code {subject_code!r}")
    if language not in LANGUAGE_CODES:
        raise ValueError(f"{row['source_id']}: unknown language {language!r}")
    grade = int(row["grade"])
    file_name = _text(row, "document_file_name")
    source_location = None
    if file_name:
        subject_directory = RAW_SUBJECT_DIRECTORIES[subject_code]
        source_location = f"{RAW_SOURCE_DIRECTORY}/grade{grade}/{subject_directory}/{file_name}"
    return CurriculumSourceRecord(
        source_id=str(row["source_id"]),
        title=_text(row, "title_primary") or str(row["title_en"]),
        publisher_authority=_text(row, "authority"),
        grade=grade,
        subject=SUBJECT_NAMES[subject_code],
        language=LANGUAGE_CODES[language],
        source_type=str(row["document_type"]),
        source_location=source_location,
        source_version=_text(row, "edition_year"),
        metadata_status=MetadataStatus.PROVISIONAL,
        ingestion_status=IngestionStatus.NOT_INGESTED,
        review_status=CurriculumReviewStatus.UNREVIEWED,
        usage_rights_status=UsageRightsStatus.UNKNOWN,
    )


def build_registry(trace_sources: Path) -> tuple[CurriculumSourceRecord, ...]:
    rows = [
        json.loads(line)
        for line in trace_sources.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records = tuple(sorted((registry_record(row) for row in rows), key=lambda r: r.source_id))
    source_ids = [record.source_id for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate source_id in curriculum trace")
    return records


def render_registry(records: tuple[CurriculumSourceRecord, ...]) -> str:
    return "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n" for record in records
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trace-sources", type=Path, default=DEFAULT_TRACE_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status 1 if the registry file is missing or out of date.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rendered = render_registry(build_registry(args.trace_sources))
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.is_file() else None
        if current != rendered:
            print(f"{args.output} is out of date; rerun without --check", file=sys.stderr)
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {rendered.count(chr(10))} source records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
