from app.curriculum.application import (
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    IngestionValidationReason,
    MetadataStatus,
    UsageRightsStatus,
    validate_extracted_page_for_ingestion,
)
from app.curriculum.application.chunking import ExtractedPage


def _source(**overrides: object) -> CurriculumSourceRecord:
    values: dict[str, object] = {
        "source_id": "SYNTHETIC-UTF8-SOURCE",
        "title": "Design-authored UTF-8 fixture",
        "publisher_authority": "Synthetic research fixture",
        "grade": 4,
        "subject": "Mathematics",
        "language": "si",
        "source_type": "synthetic-test-fixture",
        "source_location": "repository://synthetic/utf8-fixture",
        "source_version": "v1",
        "metadata_status": MetadataStatus.VERIFIED,
        "ingestion_status": IngestionStatus.INGESTED,
        "review_status": CurriculumReviewStatus.APPROVED,
        "usage_rights_status": UsageRightsStatus.PERMITTED,
    }
    values.update(overrides)
    return CurriculumSourceRecord.model_validate(values)


def _page(**overrides: object) -> ExtractedPage:
    values: dict[str, object] = {
        "source_id": "SYNTHETIC-UTF8-SOURCE",
        "page_number": 3,
        "text": "භාගයක් සමාන කොටස් පෙන්වයි.",
        "conversion_status": "preserved_needs_review",
        "source_sha256": "abc",
    }
    values.update(overrides)
    return ExtractedPage.model_validate(values)


def test_approved_utf8_page_is_stable_and_eligible() -> None:
    first = validate_extracted_page_for_ingestion(_page(), _source())
    second = validate_extracted_page_for_ingestion(_page(), _source())

    assert first == second
    assert first.extraction_usable is True
    assert first.eligible_for_approved_ingestion is True
    assert first.reasons == (IngestionValidationReason.READY,)
    assert first.page_number == 3
    assert first.content_sha256


def test_extraction_success_does_not_approve_provisional_or_unknown_rights_source() -> None:
    result = validate_extracted_page_for_ingestion(
        _page(),
        _source(
            metadata_status=MetadataStatus.PROVISIONAL,
            review_status=CurriculumReviewStatus.UNREVIEWED,
            usage_rights_status=UsageRightsStatus.UNKNOWN,
        ),
    )

    assert result.extraction_usable is True
    assert result.eligible_for_approved_ingestion is False
    assert IngestionValidationReason.SOURCE_NOT_APPROVED in result.reasons


def test_empty_legacy_or_wrong_script_extraction_fails_closed() -> None:
    for page in (
        _page(text=""),
        _page(text=".Ks;h", conversion_status="conversion_unavailable"),
        _page(text="English only"),
    ):
        result = validate_extracted_page_for_ingestion(page, _source())
        assert result.extraction_usable is False
        assert result.eligible_for_approved_ingestion is False
