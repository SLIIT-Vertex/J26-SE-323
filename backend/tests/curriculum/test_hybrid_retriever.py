from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from app.config import get_settings
from app.curriculum.application.chunking import CHUNKING_VERSION
from app.curriculum.application.retrieval import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalStatus,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    UsageRightsStatus,
)
from app.curriculum.infrastructure.embeddings import (
    E5_MODEL_NAME,
    E5_MODEL_REVISION,
    CurriculumProviderUnavailable,
    E5CurriculumEmbedder,
)
from app.curriculum.infrastructure.hybrid_retriever import FUSION_METHOD, HybridCurriculumRetriever
from app.curriculum.infrastructure.models import (
    CurriculumChunkEmbeddingModel,
    CurriculumChunkModel,
    CurriculumSourceModel,
)
from app.curriculum.infrastructure.pgvector_index import (
    PGVECTOR_NEIGHBOUR_SQL,
    CurriculumVectorIndex,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONTENT = "A unit fraction names one equal part of a whole."


class FixtureEmbedder:
    """Deterministic stand-in. It does not approve a textbook or load E5."""

    model_name = E5_MODEL_NAME
    model_revision = E5_MODEL_REVISION

    def embed_query(self, text: str) -> tuple[float, ...]:
        return (1.0, 0.0)

    def embed_passages(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _text in texts)


class UnavailableEmbedder(FixtureEmbedder):
    def embed_query(self, text: str) -> tuple[float, ...]:
        raise CurriculumProviderUnavailable("embedding runtime is not installed")


class FailingEmbedder(FixtureEmbedder):
    def embed_query(self, text: str) -> tuple[float, ...]:
        raise RuntimeError("encoder failed")


def sqlite_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _upgrade(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "curriculum@head")


def _source(**overrides: object) -> CurriculumSourceRecord:
    values: dict[str, object] = {
        "source_id": "SRC-FIXTURE",
        "title": "Fixture source",
        "publisher_authority": "Fixture",
        "grade": 5,
        "subject": "Mathematics",
        "language": "si",
        "source_type": "textbook",
        "source_version": "fixture-v1",
        "metadata_status": MetadataStatus.VERIFIED,
        "ingestion_status": IngestionStatus.INGESTED,
        "review_status": CurriculumReviewStatus.APPROVED,
        "usage_rights_status": UsageRightsStatus.PERMITTED,
    }
    values.update(overrides)
    return CurriculumSourceRecord.model_validate(values)


def _chunk(chunk_id: str, **overrides: object) -> CurriculumChunk:
    values: dict[str, object] = {
        "chunk_id": chunk_id,
        "source_id": "SRC-FIXTURE",
        "source_version": "fixture-v1",
        "content": CONTENT,
        "grade": 5,
        "subject": "Mathematics",
        "language": "si",
        "skill_ids": ("MAT-FRC",),
        "page_number": 4,
        "unit_id": "G5-MAT-C03",
        "learning_outcome_id": "G5-MAT-C03-L01-O01",
        "review_status": CurriculumReviewStatus.APPROVED,
    }
    values.update(overrides)
    return CurriculumChunk.model_validate(values)


def _request(**overrides: object) -> CurriculumRetrievalRequest:
    values: dict[str, object] = {
        "learner_question": "What is a unit fraction?",
        "skill_id": "MAT-FRC",
        "grade": 5,
        "subject": "Mathematics",
        "required_language": "si",
        "unit_id": "G5-MAT-C03",
        "purpose": "CONTENT_AUTHORING",
    }
    values.update(overrides)
    return CurriculumRetrievalRequest.model_validate(values)


@pytest.fixture
def indexed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{tmp_path / 'curriculum.sqlite'}"
    _upgrade(database_url, monkeypatch)
    engine = sqlite_engine(database_url)
    session = Session(engine)
    index = CurriculumVectorIndex(session)
    index.add_source(_source(), document_sha256="abc")
    for chunk_id in ("chunk-b", "chunk-a"):
        index.add_chunk(_chunk(chunk_id))
        index.add_embedding(
            chunk_id,
            model_name=E5_MODEL_NAME,
            model_revision=E5_MODEL_REVISION,
            vector=(1.0, 0.0),
        )
    index.add_chunk(_chunk("chunk-pending", review_status=CurriculumReviewStatus.REVIEW_PENDING))
    index.add_embedding(
        "chunk-pending",
        model_name=E5_MODEL_NAME,
        model_revision=E5_MODEL_REVISION,
        vector=(1.0, 0.0),
    )
    session.commit()
    retriever = HybridCurriculumRetriever(index, FixtureEmbedder())
    yield session, index, retriever
    session.close()
    engine.dispose()
    get_settings.cache_clear()


def test_pending_chunk_is_returned_with_the_approved_chunks(indexed) -> None:
    _session, _index, retriever = indexed
    result = retriever.retrieve(_request())

    assert result.status is CurriculumRetrievalStatus.FOUND
    assert [passage.chunk.chunk_id for passage in result.passages] == [
        "chunk-a",
        "chunk-b",
        "chunk-pending",
    ]
    assert CHUNKING_VERSION in result.retriever_version
    assert E5_MODEL_REVISION in result.retriever_version
    assert FUSION_METHOD in result.retriever_version


def test_same_request_returns_the_same_chunk_order(indexed) -> None:
    _session, _index, retriever = indexed
    request = _request()
    first = retriever.retrieve(request)
    second = retriever.retrieve(request)

    assert [passage.chunk.chunk_id for passage in first.passages] == [
        passage.chunk.chunk_id for passage in second.passages
    ]


def test_limit_is_respected(indexed) -> None:
    _session, _index, retriever = indexed
    result = retriever.retrieve(_request(limit=1))

    assert [passage.chunk.chunk_id for passage in result.passages] == ["chunk-a"]


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"grade": 4}, CurriculumRetrievalStatus.NO_APPROVED_SOURCE),
        ({"subject": "Science"}, CurriculumRetrievalStatus.NO_APPROVED_SOURCE),
        ({"required_language": "en"}, CurriculumRetrievalStatus.NO_APPROVED_SOURCE),
        ({"unit_id": "OTHER-UNIT"}, CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES),
        ({"skill_id": "OTHER-SKILL"}, CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES),
    ],
)
def test_mismatched_filters_return_no_passage(
    indexed, overrides: dict[str, object], status
) -> None:
    _session, _index, retriever = indexed
    result = retriever.retrieve(_request(**overrides))

    assert result.passages == ()
    assert result.status is status


def test_requested_language_is_a_preference_not_a_hard_filter(indexed) -> None:
    _session, _index, retriever = indexed
    result = retriever.retrieve(_request(requested_language="en"))

    assert [passage.chunk.chunk_id for passage in result.passages] == [
        "chunk-a",
        "chunk-b",
        "chunk-pending",
    ]


def test_unknown_usage_rights_still_return_the_chunks(indexed) -> None:
    session, _index, retriever = indexed
    source = session.get(CurriculumSourceModel, "SRC-FIXTURE")
    assert source is not None
    source.usage_rights_status = UsageRightsStatus.UNKNOWN.value
    session.commit()

    result = retriever.retrieve(_request())

    assert [passage.chunk.chunk_id for passage in result.passages] == [
        "chunk-a",
        "chunk-b",
        "chunk-pending",
    ]


@pytest.mark.parametrize("rights", [UsageRightsStatus.RESTRICTED])
def test_restricted_usage_rights_return_nothing(indexed, rights: UsageRightsStatus) -> None:
    session, _index, retriever = indexed
    source = session.get(CurriculumSourceModel, "SRC-FIXTURE")
    assert source is not None
    source.usage_rights_status = rights.value
    session.commit()

    result = retriever.retrieve(_request())

    assert result.passages == ()
    assert result.status is CurriculumRetrievalStatus.NO_APPROVED_SOURCE


def test_embedding_runtime_missing_returns_no_passages(indexed) -> None:
    _session, index, _retriever = indexed
    result = HybridCurriculumRetriever(index, UnavailableEmbedder()).retrieve(_request())

    assert result.status is CurriculumRetrievalStatus.PROVIDER_UNAVAILABLE
    assert result.passages == ()


def test_embedding_failure_returns_no_passages(indexed) -> None:
    _session, index, _retriever = indexed
    result = HybridCurriculumRetriever(index, FailingEmbedder()).retrieve(_request())

    assert result.status is CurriculumRetrievalStatus.PROVIDER_ERROR
    assert result.passages == ()


def test_database_failure_returns_no_passages(indexed) -> None:
    _session, index, retriever = indexed

    def fail(_request: CurriculumRetrievalRequest) -> bool:
        raise OperationalError("SELECT", {}, OSError("database closed"))

    index.has_approved_source = fail  # type: ignore[method-assign]
    result = retriever.retrieve(_request())

    assert result.status is CurriculumRetrievalStatus.PROVIDER_ERROR
    assert result.passages == ()


def test_deleting_a_source_removes_chunks_and_embeddings(indexed) -> None:
    session, index, _retriever = indexed
    index.delete_source("SRC-FIXTURE")
    session.commit()

    assert session.scalars(select(CurriculumSourceModel)).all() == []
    assert session.scalars(select(CurriculumChunkModel)).all() == []
    assert session.scalars(select(CurriculumChunkEmbeddingModel)).all() == []


def test_a_new_embedding_revision_keeps_the_previous_row(indexed) -> None:
    session, index, _retriever = indexed
    index.add_embedding(
        "chunk-a",
        model_name=E5_MODEL_NAME,
        model_revision="previous-revision",
        vector=(0.0, 1.0),
    )
    session.commit()
    rows = session.scalars(
        select(CurriculumChunkEmbeddingModel).where(
            CurriculumChunkEmbeddingModel.chunk_id == "chunk-a"
        )
    ).all()

    stored = {row.model_revision: tuple(row.vector) for row in rows}
    assert stored[E5_MODEL_REVISION] == (1.0, 0.0)
    assert stored["previous-revision"] == (0.0, 1.0)


def test_pgvector_ranking_uses_cosine_distance_and_chunk_id_order() -> None:
    assert "curriculum_chunk_embeddings" in PGVECTOR_NEIGHBOUR_SQL
    assert "<=>" in PGVECTOR_NEIGHBOUR_SQL
    assert "chunk_id ASC" in PGVECTOR_NEIGHBOUR_SQL


def test_e5_adapter_records_the_shared_revision_without_loading_it() -> None:
    embedder = E5CurriculumEmbedder()

    assert embedder.model_name == E5_MODEL_NAME
    assert embedder.model_revision == E5_MODEL_REVISION
    assert embedder._model is None
