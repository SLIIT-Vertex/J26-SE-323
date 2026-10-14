from typing import Protocol

from app.curriculum.application.retrieval import CurriculumSourceRecord


class CurriculumSourceRegistry(Protocol):
    def list_sources(self) -> tuple[CurriculumSourceRecord, ...]: ...

    def get_source(self, source_id: str) -> CurriculumSourceRecord | None: ...
