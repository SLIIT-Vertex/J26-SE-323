"""Load one Universal skill's chunks into the shared curriculum tables.

The hash embedder keeps this path runnable without downloading a model. A later
E5 index uses the same tables and a new embedding revision.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.curriculum.application.chunking import read_curriculum_jsonl
from app.curriculum.application.retrieval import CurriculumChunk, CurriculumSourceRecord
from app.curriculum.infrastructure.hybrid_retriever import HybridCurriculumRetriever
from app.curriculum.infrastructure.models import (
    CurriculumChunkEmbeddingModel,
    CurriculumChunkModel,
    CurriculumSourceModel,
)
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.shared.database.base import Base

PILOT_EMBEDDING_REVISION = "pilot-hash-v1"


class PilotHashEmbedder:
    """Fixed hash vectors. Construction does not download a model."""

    model_name = "pilot-hash"
    model_revision = PILOT_EMBEDDING_REVISION

    def embed_query(self, text: str) -> tuple[float, ...]:
        return _hash_vector(text)

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(_hash_vector(text) for text in texts)


def open_skill_retriever(
    database_url: str,
    chunks_path: Path,
    registry_path: Path,
    skill_id: str,
) -> tuple[Engine, Session, HybridCurriculumRetriever, int]:
    embedder = PilotHashEmbedder()
    engine, session, loaded = load_skill_chunks(
        database_url,
        chunks_path,
        registry_path,
        skill_id,
        embedder,
    )
    retriever = HybridCurriculumRetriever(CurriculumVectorIndex(session), embedder)
    return engine, session, retriever, loaded


def load_skill_chunks(
    database_url: str,
    chunks_path: Path,
    registry_path: Path,
    skill_id: str,
    embedder: PilotHashEmbedder,
) -> tuple[Engine, Session, int]:
    sqlite_path = _sqlite_path(database_url)
    if sqlite_path is not None and sqlite_path.exists():
        sqlite_path.unlink()
    engine = create_engine(database_url)
    Base.metadata.create_all(
        engine,
        tables=[
            CurriculumSourceModel.__table__,
            CurriculumChunkModel.__table__,
            CurriculumChunkEmbeddingModel.__table__,
        ],
    )
    session = Session(engine)
    index = CurriculumVectorIndex(session)
    sources = {
        str(row["source_id"]): CurriculumSourceRecord.model_validate(row)
        for row in read_curriculum_jsonl(registry_path)
    }
    added: set[str] = set()
    loaded = 0
    for row in read_curriculum_jsonl(chunks_path):
        payload = {
            key: value
            for key, value in row.items()
            if key not in {"chunking_version", "transcription_method"}
        }
        chunk = CurriculumChunk.model_validate(payload)
        if skill_id not in chunk.skill_ids:
            continue
        if chunk.source_id not in added:
            index.add_source(sources[chunk.source_id])
            added.add(chunk.source_id)
        index.add_chunk(chunk, chunking_version=str(row["chunking_version"]))
        index.add_embedding(
            chunk.chunk_id,
            model_name=embedder.model_name,
            model_revision=embedder.model_revision,
            vector=embedder.embed_passages((chunk.content,))[0],
        )
        loaded += 1
    session.commit()
    return engine, session, loaded


def _hash_vector(text: str) -> tuple[float, ...]:
    digest = hashlib.sha256(text.encode()).digest()
    return tuple(byte / 255 for byte in digest[:8])


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))
