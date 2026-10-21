"""Explicitly reviewed curriculum import for the local researcher workflow."""

import hashlib
from collections.abc import Collection, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.curriculum.application.chunking import ExtractedPage, split_page_paragraphs
from app.curriculum.application.ingestion_validation import (
    validate_extracted_page_for_ingestion,
)
from app.curriculum.application.retrieval import (
    CurriculumChunk,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    NonBlankText,
    UsageRightsStatus,
    validate_curriculum_skill_ids,
)


class ResearchCurriculumEmbedder(Protocol):
    model_name: str
    model_revision: str

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


class ResearchCurriculumIndex(Protocol):
    def add_source(
        self, source: CurriculumSourceRecord, *, document_sha256: str | None = None
    ) -> None: ...

    def add_chunk(
        self, chunk: CurriculumChunk, *, chunking_version: str = "chunking-v1"
    ) -> None: ...

    def add_embedding(
        self,
        chunk_id: str,
        *,
        model_name: str,
        model_revision: str,
        vector: Sequence[float],
    ) -> None: ...


class ResearchCurriculumApproval(BaseModel):
    """Human assertions required before software may promote and index a source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: NonBlankText
    approval_reference: NonBlankText
    rights_basis: NonBlankText
    skill_ids: tuple[NonBlankText, ...] = Field(min_length=1)


class ResearchCurriculumImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    source_version: NonBlankText
    chunk_ids: tuple[NonBlankText, ...]
    reviewer_id: NonBlankText
    approval_reference: NonBlankText
    rights_basis: NonBlankText
    document_sha256: NonBlankText


class ResearchCurriculumImporter:
    """Validate, chunk, embed and stage one explicitly approved UTF-8 source.

    The caller owns the database transaction. This service never interprets a
    provisional source as approved and never changes review or rights states.
    """

    def __init__(
        self,
        index: ResearchCurriculumIndex,
        embedder: ResearchCurriculumEmbedder,
        valid_skill_ids: Collection[str],
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._valid_skill_ids = frozenset(valid_skill_ids)

    def import_pages(
        self,
        *,
        source: CurriculumSourceRecord,
        pages: tuple[ExtractedPage, ...],
        approval: ResearchCurriculumApproval,
    ) -> ResearchCurriculumImportResult:
        if not pages:
            raise ValueError("at least one reviewed curriculum page is required")
        self._validate_source_approval(source)
        if source.source_version is None:
            raise ValueError("approved source requires a version")

        ingested_source = source.model_copy(update={"ingestion_status": IngestionStatus.INGESTED})
        chunks: list[CurriculumChunk] = []
        page_hashes: list[str] = []
        for page in pages:
            validation = validate_extracted_page_for_ingestion(page, ingested_source)
            if not validation.eligible_for_approved_ingestion or validation.content_sha256 is None:
                reasons = ", ".join(reason.value for reason in validation.reasons)
                raise ValueError(f"page {page.page_number} is not eligible: {reasons}")
            page_hashes.append(validation.content_sha256)
            for position, content in enumerate(split_page_paragraphs(page.text or ""), start=1):
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                chunks.append(
                    CurriculumChunk(
                        chunk_id=(
                            f"{source.source_id}:p{page.page_number:04d}:"
                            f"research-reviewed:{position:04d}:{digest}"
                        ),
                        source_id=source.source_id,
                        source_version=source.source_version,
                        content=content,
                        grade=source.grade,
                        subject=source.subject,
                        language=source.language,
                        skill_ids=approval.skill_ids,
                        page_number=page.page_number,
                        section_locator=f"research-review:{approval.approval_reference}",
                        review_status=CurriculumReviewStatus.APPROVED,
                    )
                )
        if not chunks:
            raise ValueError("reviewed curriculum pages produced no chunks")
        for chunk in chunks:
            validate_curriculum_skill_ids(chunk, self._valid_skill_ids)

        # Complete all external/model work before staging database mutations.
        vectors = self._embedder.embed_passages(tuple(chunk.content for chunk in chunks))
        if len(vectors) != len(chunks):
            raise ValueError("embedding provider returned the wrong number of vectors")
        document_sha256 = hashlib.sha256("".join(page_hashes).encode()).hexdigest()
        self._index.add_source(ingested_source, document_sha256=document_sha256)
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._index.add_chunk(chunk)
            self._index.add_embedding(
                chunk.chunk_id,
                model_name=self._embedder.model_name,
                model_revision=self._embedder.model_revision,
                vector=vector,
            )
        return ResearchCurriculumImportResult(
            source_id=source.source_id,
            source_version=source.source_version,
            chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
            reviewer_id=approval.reviewer_id,
            approval_reference=approval.approval_reference,
            rights_basis=approval.rights_basis,
            document_sha256=document_sha256,
        )

    @staticmethod
    def _validate_source_approval(source: CurriculumSourceRecord) -> None:
        if source.metadata_status is not MetadataStatus.VERIFIED:
            raise ValueError("source metadata is not verified")
        if source.ingestion_status is not IngestionStatus.READY:
            raise ValueError("source must be explicitly marked ready for ingestion")
        if source.review_status is not CurriculumReviewStatus.APPROVED:
            raise ValueError("source is not human-approved")
        if source.usage_rights_status is not UsageRightsStatus.PERMITTED:
            raise ValueError("source usage rights are not explicitly permitted")
        if not all(
            (
                source.publisher_authority,
                source.source_location,
                source.source_version,
                source.grade,
                source.subject,
                source.language,
            )
        ):
            raise ValueError("source ownership, scope, and version metadata are incomplete")
