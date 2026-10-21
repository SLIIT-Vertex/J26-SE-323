import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.curriculum.application import (
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    ResearchCurriculumApproval,
    ResearchCurriculumImporter,
    UsageRightsStatus,
)
from app.curriculum.application.chunking import ExtractedPage
from app.curriculum.infrastructure.models import (
    CurriculumChunkEmbeddingModel,
    CurriculumChunkModel,
    CurriculumSourceModel,
)
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.shared.database.base import Base


class FixtureEmbedder:
    model_name = "fixture-embedder"
    model_revision = "v1"

    def embed_passages(self, texts):
        return tuple((1.0, float(index)) for index, _text in enumerate(texts))


def source(**overrides: object) -> CurriculumSourceRecord:
    values: dict[str, object] = {
        "source_id": "RESEARCH-OWNED-001",
        "title": "Researcher-authored fractions note",
        "publisher_authority": "MindBridge research team",
        "grade": 4,
        "subject": "Mathematics",
        "language": "en",
        "source_type": "researcher-authored",
        "source_location": "repository://research/curriculum/fractions-v1.txt",
        "source_version": "v1",
        "metadata_status": MetadataStatus.VERIFIED,
        "ingestion_status": IngestionStatus.READY,
        "review_status": CurriculumReviewStatus.APPROVED,
        "usage_rights_status": UsageRightsStatus.PERMITTED,
    }
    values.update(overrides)
    return CurriculumSourceRecord.model_validate(values)


def approval() -> ResearchCurriculumApproval:
    return ResearchCurriculumApproval(
        reviewer_id="adult-reviewer-001",
        approval_reference="review-2026-10-19-001",
        rights_basis="Original text authored by the named research team",
        skill_ids=("MAT-FRC",),
    )


def importer(session: Session) -> ResearchCurriculumImporter:
    return ResearchCurriculumImporter(
        CurriculumVectorIndex(session), FixtureEmbedder(), {"MAT-FRC"}
    )


def test_explicitly_approved_utf8_source_is_chunked_and_indexed() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = importer(session).import_pages(
            source=source(),
            pages=(
                ExtractedPage(
                    source_id="RESEARCH-OWNED-001",
                    page_number=1,
                    text="A fraction names equal parts of one whole.\n\nThe denominator names the number of equal parts.",
                    conversion_status="preserved_needs_review",
                ),
            ),
            approval=approval(),
        )
        session.commit()

        stored_source = session.get(CurriculumSourceModel, result.source_id)
        chunks = session.scalars(select(CurriculumChunkModel)).all()
        embeddings = session.scalars(select(CurriculumChunkEmbeddingModel)).all()
        assert stored_source is not None
        assert stored_source.ingestion_status == IngestionStatus.INGESTED.value
        assert len(chunks) == len(embeddings) == len(result.chunk_ids) == 2
        assert all(chunk.review_status == CurriculumReviewStatus.APPROVED.value for chunk in chunks)


@pytest.mark.parametrize(
    "unapproved",
    (
        source(metadata_status=MetadataStatus.PROVISIONAL),
        source(review_status=CurriculumReviewStatus.REVIEW_PENDING),
        source(usage_rights_status=UsageRightsStatus.UNKNOWN),
    ),
)
def test_import_never_promotes_unapproved_or_unknown_rights_source(
    unapproved: CurriculumSourceRecord,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError):
            importer(session).import_pages(
                source=unapproved,
                pages=(
                    ExtractedPage(
                        source_id=unapproved.source_id,
                        page_number=1,
                        text="Reviewed English curriculum text.",
                        conversion_status="preserved_needs_review",
                    ),
                ),
                approval=approval(),
            )
        assert session.get(CurriculumSourceModel, unapproved.source_id) is None


def test_invalid_sinhala_extraction_is_rejected_before_index_mutation() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="not eligible"):
            importer(session).import_pages(
                source=source(language="si"),
                pages=(
                    ExtractedPage(
                        source_id="RESEARCH-OWNED-001",
                        page_number=1,
                        text=".Ks;h invalid legacy extraction",
                        conversion_status="conversion_unavailable",
                    ),
                ),
                approval=approval(),
            )
        assert session.scalar(select(CurriculumChunkModel)) is None
