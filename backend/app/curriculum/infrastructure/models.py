"""SQLAlchemy models for the shared curriculum index."""

from sqlalchemy import JSON, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class CurriculumSourceModel(Base):
    __tablename__ = "curriculum_sources"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    publisher_authority: Mapped[str | None] = mapped_column(String(512))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    subject: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(64))
    source_location: Mapped[str | None] = mapped_column(String(512))
    source_version: Mapped[str | None] = mapped_column(String(128))
    source_document_sha256: Mapped[str | None] = mapped_column(String(64))
    metadata_status: Mapped[str] = mapped_column(String(32))
    ingestion_status: Mapped[str] = mapped_column(String(32))
    review_status: Mapped[str] = mapped_column(String(32))
    usage_rights_status: Mapped[str] = mapped_column(String(32))


class CurriculumChunkModel(Base):
    __tablename__ = "curriculum_chunks"

    chunk_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_sources.source_id", ondelete="CASCADE")
    )
    source_version: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    grade: Mapped[int] = mapped_column(SmallInteger)
    subject: Mapped[str] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(16))
    skill_ids: Mapped[list[str]] = mapped_column(JsonType)
    page_number: Mapped[int | None] = mapped_column()
    section_locator: Mapped[str | None] = mapped_column(String(512))
    unit_id: Mapped[str | None] = mapped_column(String(128))
    learning_outcome_id: Mapped[str | None] = mapped_column(String(128))
    review_status: Mapped[str] = mapped_column(String(32))
    chunking_version: Mapped[str] = mapped_column(String(64))


class CurriculumChunkEmbeddingModel(Base):
    __tablename__ = "curriculum_chunk_embeddings"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    model_revision: Mapped[str] = mapped_column(String(128), primary_key=True)
    vector: Mapped[list[float]] = mapped_column(JSON)
