import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.curriculum.application import (
    CurriculumReviewStatus,
    CurriculumSourceRegistry,
    IngestionStatus,
    MetadataStatus,
    UsageRightsStatus,
)
from app.curriculum.infrastructure import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    JsonlCurriculumSourceRegistry,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "backend/scripts/build_curriculum_source_registry.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("curriculum_source_registry", SCRIPT_PATH)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = SCRIPT
SCRIPT_SPEC.loader.exec_module(SCRIPT)

TRACE_SOURCE_ROW = {
    "source_id": "SRC-TEST-01",
    "subject": "MAT",
    "grade": 5,
    "language": "Sinhala",
    "document_type": "textbook",
    "document_file_name": "test.pdf",
    "title_primary": "",
    "title_en": "Test book",
    "authority": "",
    "edition_year": "2019",
}


def test_committed_registry_matches_the_trace() -> None:
    expected = SCRIPT.render_registry(SCRIPT.build_registry(SCRIPT.DEFAULT_TRACE_SOURCES))

    assert DEFAULT_SOURCE_REGISTRY_PATH == SCRIPT.DEFAULT_REGISTRY
    assert DEFAULT_SOURCE_REGISTRY_PATH.read_text(encoding="utf-8") == expected


def test_registry_loads_every_trace_source_as_unapproved() -> None:
    registry: CurriculumSourceRegistry = JsonlCurriculumSourceRegistry()
    trace_ids = {
        json.loads(line)["source_id"]
        for line in SCRIPT.DEFAULT_TRACE_SOURCES.read_text(encoding="utf-8").splitlines()
    }
    records = registry.list_sources()

    assert {record.source_id for record in records} == trace_ids
    assert len(records) == 17
    assert {record.language for record in records} == {"si", "en"}
    assert all(record.grade == 5 for record in records)
    assert {record.metadata_status for record in records} == {MetadataStatus.PROVISIONAL}
    assert {record.ingestion_status for record in records} == {IngestionStatus.NOT_INGESTED}
    assert {record.review_status for record in records} == {CurriculumReviewStatus.UNREVIEWED}
    assert {record.usage_rights_status for record in records} == {UsageRightsStatus.UNKNOWN}
    assert registry.get_source("SRC-G5-MAT-TB-01") is not None
    assert registry.get_source("SRC-UNKNOWN") is None


def test_registry_record_falls_back_and_omits_blank_fields() -> None:
    record = SCRIPT.registry_record(TRACE_SOURCE_ROW)

    assert record.title == "Test book"
    assert record.publisher_authority is None
    assert record.subject == "Mathematics"
    assert record.language == "si"
    assert record.source_location == "data/curriculum/raw/grade5/mathematics/test.pdf"


def test_local_source_pdfs_match_registry_locations() -> None:
    raw_directory = REPOSITORY_ROOT / SCRIPT.RAW_SOURCE_DIRECTORY
    if not raw_directory.is_dir():
        pytest.skip("source PDFs are not present locally")
    expected = {record.source_location for record in JsonlCurriculumSourceRegistry().list_sources()}
    present = {
        path.relative_to(REPOSITORY_ROOT).as_posix() for path in raw_directory.rglob("*.pdf")
    }

    assert expected <= present


@pytest.mark.parametrize(("field", "value"), [("language", "Tamil"), ("subject", "ART")])
def test_registry_record_rejects_unmapped_values(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="unknown"):
        SCRIPT.registry_record({**TRACE_SOURCE_ROW, field: value})


def test_registry_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    line = DEFAULT_SOURCE_REGISTRY_PATH.read_text(encoding="utf-8").splitlines()[0]
    duplicate = tmp_path / "sources.jsonl"
    duplicate.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate source_id"):
        JsonlCurriculumSourceRegistry(duplicate)
