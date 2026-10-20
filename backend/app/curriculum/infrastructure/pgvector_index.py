"""Shared curriculum index. PostgreSQL ranks vectors with pgvector cosine distance."""

from collections.abc import Sequence

from sqlalchemy import bindparam, delete, select, text
from sqlalchemy.orm import Session

from app.curriculum.application.chunking import CHUNKING_VERSION
from app.curriculum.application.retrieval import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    UsageRightsStatus,
)
from app.curriculum.infrastructure.models import (
    CurriculumChunkEmbeddingModel,
    CurriculumChunkModel,
    CurriculumSourceModel,
)

PGVECTOR_NEIGHBOUR_SQL = """
SELECT chunk_id
FROM curriculum_chunk_embeddings
WHERE model_name = :model_name
  AND model_revision = :model_revision
  AND chunk_id IN :chunk_ids
ORDER BY vector <=> CAST(:query_vector AS vector), chunk_id ASC
"""


class IndexedChunk:
    def __init__(
        self,
        chunk: CurriculumChunk,
        source: CurriculumSourceRecord,
    ) -> None:
        self.chunk = chunk
        self.source = source


class CurriculumVectorIndex:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_source(
        self,
        source: CurriculumSourceRecord,
        *,
        document_sha256: str | None = None,
    ) -> None:
        row = self._session.get(CurriculumSourceModel, source.source_id)
        values = _source_values(source, document_sha256)
        if row is None:
            self._session.add(CurriculumSourceModel(**values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        self._session.flush()

    def add_chunk(
        self,
        chunk: CurriculumChunk,
        *,
        chunking_version: str = CHUNKING_VERSION,
    ) -> None:
        row = self._session.get(CurriculumChunkModel, chunk.chunk_id)
        values = _chunk_values(chunk, chunking_version)
        if row is None:
            self._session.add(CurriculumChunkModel(**values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        self._session.flush()

    def add_embedding(
        self,
        chunk_id: str,
        *,
        model_name: str,
        model_revision: str,
        vector: Sequence[float],
    ) -> None:
        """Store one revision. A different revision inserts a new row."""

        if self._postgres:
            literal = "[" + ",".join(str(float(value)) for value in vector) + "]"
            self._session.execute(
                text(
                    """
                    INSERT INTO curriculum_chunk_embeddings (
                        chunk_id, model_name, model_revision, vector
                    )
                    VALUES (
                        :chunk_id, :model_name, :model_revision, CAST(:vector AS vector)
                    )
                    ON CONFLICT (chunk_id, model_name, model_revision)
                    DO UPDATE SET vector = EXCLUDED.vector
                    """
                ),
                {
                    "chunk_id": chunk_id,
                    "model_name": model_name,
                    "model_revision": model_revision,
                    "vector": literal,
                },
            )
            self._session.flush()
            return
        key = (chunk_id, model_name, model_revision)
        row = self._session.get(CurriculumChunkEmbeddingModel, key)
        stored = [float(value) for value in vector]
        if row is None:
            self._session.add(
                CurriculumChunkEmbeddingModel(
                    chunk_id=chunk_id,
                    model_name=model_name,
                    model_revision=model_revision,
                    vector=stored,
                )
            )
        else:
            row.vector = stored
        self._session.flush()

    def delete_source(self, source_id: str) -> None:
        chunk_ids = list(
            self._session.scalars(
                select(CurriculumChunkModel.chunk_id).where(
                    CurriculumChunkModel.source_id == source_id
                )
            )
        )
        if chunk_ids:
            self._session.execute(
                delete(CurriculumChunkEmbeddingModel).where(
                    CurriculumChunkEmbeddingModel.chunk_id.in_(chunk_ids)
                )
            )
            self._session.execute(
                delete(CurriculumChunkModel).where(CurriculumChunkModel.source_id == source_id)
            )
        self._session.execute(
            delete(CurriculumSourceModel).where(CurriculumSourceModel.source_id == source_id)
        )
        self._session.flush()

    def has_approved_source(self, request: CurriculumRetrievalRequest) -> bool:
        statement = select(CurriculumSourceModel.source_id).where(
            CurriculumSourceModel.metadata_status == MetadataStatus.VERIFIED.value,
            CurriculumSourceModel.ingestion_status == IngestionStatus.INGESTED.value,
            CurriculumSourceModel.review_status == CurriculumReviewStatus.APPROVED.value,
            CurriculumSourceModel.usage_rights_status == UsageRightsStatus.PERMITTED.value,
            CurriculumSourceModel.publisher_authority.is_not(None),
            CurriculumSourceModel.source_location.is_not(None),
            CurriculumSourceModel.source_version.is_not(None),
            CurriculumSourceModel.grade == request.grade,
            CurriculumSourceModel.subject.is_not(None),
            CurriculumSourceModel.language.is_not(None),
        )
        if request.subject is not None:
            statement = statement.where(CurriculumSourceModel.subject == request.subject)
        if request.required_language is not None:
            statement = statement.where(CurriculumSourceModel.language == request.required_language)
        return self._session.scalars(statement).first() is not None

    def approved_chunks(self, request: CurriculumRetrievalRequest) -> tuple[IndexedChunk, ...]:
        statement = (
            select(CurriculumChunkModel, CurriculumSourceModel)
            .join(
                CurriculumSourceModel,
                CurriculumSourceModel.source_id == CurriculumChunkModel.source_id,
            )
            .where(
                CurriculumSourceModel.metadata_status == MetadataStatus.VERIFIED.value,
                CurriculumSourceModel.ingestion_status == IngestionStatus.INGESTED.value,
                CurriculumSourceModel.review_status == CurriculumReviewStatus.APPROVED.value,
                CurriculumSourceModel.usage_rights_status == UsageRightsStatus.PERMITTED.value,
                CurriculumSourceModel.publisher_authority.is_not(None),
                CurriculumSourceModel.source_location.is_not(None),
                CurriculumSourceModel.source_version.is_not(None),
                CurriculumChunkModel.review_status == CurriculumReviewStatus.APPROVED.value,
                CurriculumChunkModel.grade == request.grade,
                CurriculumSourceModel.grade == CurriculumChunkModel.grade,
                CurriculumSourceModel.subject == CurriculumChunkModel.subject,
                CurriculumSourceModel.language == CurriculumChunkModel.language,
                CurriculumSourceModel.source_version == CurriculumChunkModel.source_version,
                (CurriculumChunkModel.page_number.is_not(None))
                | (CurriculumChunkModel.section_locator.is_not(None)),
            )
        )
        if request.subject is not None:
            statement = statement.where(CurriculumChunkModel.subject == request.subject)
        if request.required_language is not None:
            statement = statement.where(CurriculumChunkModel.language == request.required_language)
        if request.unit_id is not None:
            statement = statement.where(CurriculumChunkModel.unit_id == request.unit_id)
        rows = self._session.execute(statement).all()
        passages: list[IndexedChunk] = []
        for chunk_row, source_row in rows:
            if request.skill_id not in list(chunk_row.skill_ids):
                continue
            passages.append(IndexedChunk(_chunk_record(chunk_row), _source_record(source_row)))
        return tuple(passages)

    def rank_by_vector(
        self,
        query_vector: Sequence[float],
        chunk_ids: Sequence[str],
        *,
        model_name: str,
        model_revision: str,
    ) -> tuple[str, ...]:
        if not chunk_ids:
            return ()
        if self._postgres:
            return self._rank_pgvector(query_vector, chunk_ids, model_name, model_revision)
        return self._rank_cosine(query_vector, chunk_ids, model_name, model_revision)

    @property
    def _postgres(self) -> bool:
        return self._session.get_bind().dialect.name == "postgresql"

    def _rank_pgvector(
        self,
        query_vector: Sequence[float],
        chunk_ids: Sequence[str],
        model_name: str,
        model_revision: str,
    ) -> tuple[str, ...]:
        literal = "[" + ",".join(str(float(value)) for value in query_vector) + "]"
        statement = text(PGVECTOR_NEIGHBOUR_SQL).bindparams(bindparam("chunk_ids", expanding=True))
        rows = self._session.execute(
            statement,
            {
                "model_name": model_name,
                "model_revision": model_revision,
                "chunk_ids": list(chunk_ids),
                "query_vector": literal,
            },
        ).all()
        return tuple(str(row[0]) for row in rows)

    def _rank_cosine(
        self,
        query_vector: Sequence[float],
        chunk_ids: Sequence[str],
        model_name: str,
        model_revision: str,
    ) -> tuple[str, ...]:
        rows = self._session.scalars(
            select(CurriculumChunkEmbeddingModel).where(
                CurriculumChunkEmbeddingModel.model_name == model_name,
                CurriculumChunkEmbeddingModel.model_revision == model_revision,
                CurriculumChunkEmbeddingModel.chunk_id.in_(list(chunk_ids)),
            )
        ).all()
        scored = [(row.chunk_id, _cosine(query_vector, row.vector)) for row in rows]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return tuple(chunk_id for chunk_id, _score in scored)


def _source_values(
    source: CurriculumSourceRecord,
    document_sha256: str | None,
) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "title": source.title,
        "publisher_authority": source.publisher_authority,
        "grade": source.grade,
        "subject": source.subject,
        "language": source.language,
        "source_type": source.source_type,
        "source_location": source.source_location,
        "source_version": source.source_version,
        "source_document_sha256": document_sha256,
        "metadata_status": source.metadata_status.value,
        "ingestion_status": source.ingestion_status.value,
        "review_status": source.review_status.value,
        "usage_rights_status": source.usage_rights_status.value,
    }


def _chunk_values(chunk: CurriculumChunk, chunking_version: str) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "source_version": chunk.source_version,
        "content": chunk.content,
        "grade": chunk.grade,
        "subject": chunk.subject,
        "language": chunk.language,
        "skill_ids": list(chunk.skill_ids),
        "page_number": chunk.page_number,
        "section_locator": chunk.section_locator,
        "unit_id": chunk.unit_id,
        "learning_outcome_id": chunk.learning_outcome_id,
        "review_status": chunk.review_status.value,
        "chunking_version": chunking_version,
    }


def _chunk_record(row: CurriculumChunkModel) -> CurriculumChunk:
    return CurriculumChunk(
        chunk_id=row.chunk_id,
        source_id=row.source_id,
        source_version=row.source_version,
        content=row.content,
        grade=row.grade,
        subject=row.subject,
        language=row.language,
        skill_ids=tuple(row.skill_ids),
        page_number=row.page_number,
        section_locator=row.section_locator,
        unit_id=row.unit_id,
        learning_outcome_id=row.learning_outcome_id,
        review_status=row.review_status,
    )


def _source_record(row: CurriculumSourceModel) -> CurriculumSourceRecord:
    return CurriculumSourceRecord(
        source_id=row.source_id,
        title=row.title,
        publisher_authority=row.publisher_authority,
        grade=row.grade,
        subject=row.subject,
        language=row.language,
        source_type=row.source_type,
        source_location=row.source_location,
        source_version=row.source_version,
        metadata_status=row.metadata_status,
        ingestion_status=row.ingestion_status,
        review_status=row.review_status,
        usage_rights_status=row.usage_rights_status,
    )


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    left_norm = sum(float(value) * float(value) for value in left) ** 0.5
    right_norm = sum(float(value) * float(value) for value in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
