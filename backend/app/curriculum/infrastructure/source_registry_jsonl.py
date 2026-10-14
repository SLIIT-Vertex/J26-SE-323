from pathlib import Path

from app.curriculum.application.retrieval import CurriculumSourceRecord

DEFAULT_SOURCE_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "curriculum"
    / "registry"
    / "v1"
    / "sources.jsonl"
)


class JsonlCurriculumSourceRegistry:
    """Read-only source registry backed by one JSON object per line."""

    def __init__(self, path: Path = DEFAULT_SOURCE_REGISTRY_PATH) -> None:
        records = tuple(
            CurriculumSourceRecord.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        by_id = {record.source_id: record for record in records}
        if len(by_id) != len(records):
            raise ValueError(f"duplicate source_id in curriculum source registry {path}")
        self._records = records
        self._by_id = by_id

    def list_sources(self) -> tuple[CurriculumSourceRecord, ...]:
        return self._records

    def get_source(self, source_id: str) -> CurriculumSourceRecord | None:
        return self._by_id.get(source_id)
