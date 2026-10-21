"""Fail-closed validation between extraction and approved curriculum ingestion."""

import hashlib
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.curriculum.application.chunking import ExtractedPage
from app.curriculum.application.retrieval import (
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    UsageRightsStatus,
)


class IngestionValidationReason(StrEnum):
    READY = "READY"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    EXTRACTION_INCOMPLETE = "EXTRACTION_INCOMPLETE"
    EMPTY = "EMPTY"
    INVALID_UNICODE = "INVALID_UNICODE"
    GARBLED = "GARBLED"
    LANGUAGE_MISMATCH = "LANGUAGE_MISMATCH"
    SOURCE_NOT_APPROVED = "SOURCE_NOT_APPROVED"


class IngestionValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    extraction_usable: bool
    eligible_for_approved_ingestion: bool
    reasons: tuple[IngestionValidationReason, ...]
    source_id: str
    page_number: int
    content_sha256: str | None = None


_SUCCESSFUL_EXTRACTION_STATUSES = frozenset({"preserved_needs_review", "converted_needs_review"})
_SCRIPTS = {
    "en": ("LATIN",),
    "si": ("SINHALA",),
    "ta": ("TAMIL",),
}


def validate_extracted_page_for_ingestion(
    page: ExtractedPage,
    source: CurriculumSourceRecord,
) -> IngestionValidationResult:
    """Validate UTF-8 text and approval independently, preserving page provenance.

    The stable content hash makes repeated ingestion idempotency checks possible; this
    function never upgrades review, rights, or ingestion status itself.
    """

    reasons: list[IngestionValidationReason] = []
    text = page.text or ""
    if page.source_id != source.source_id:
        reasons.append(IngestionValidationReason.SOURCE_MISMATCH)
    if page.conversion_status not in _SUCCESSFUL_EXTRACTION_STATUSES:
        reasons.append(IngestionValidationReason.EXTRACTION_INCOMPLETE)
    if not text.strip():
        reasons.append(IngestionValidationReason.EMPTY)
    try:
        encoded = text.encode("utf-8", errors="strict")
    except UnicodeError:
        encoded = b""
        reasons.append(IngestionValidationReason.INVALID_UNICODE)
    if text and _looks_garbled(text):
        reasons.append(IngestionValidationReason.GARBLED)
    if (
        text
        and source.language not in _SCRIPTS
        or text
        and not _has_expected_script(text, source.language or "")
    ):
        reasons.append(IngestionValidationReason.LANGUAGE_MISMATCH)

    extraction_usable = not any(
        reason
        in {
            IngestionValidationReason.SOURCE_MISMATCH,
            IngestionValidationReason.EXTRACTION_INCOMPLETE,
            IngestionValidationReason.EMPTY,
            IngestionValidationReason.INVALID_UNICODE,
            IngestionValidationReason.GARBLED,
            IngestionValidationReason.LANGUAGE_MISMATCH,
        }
        for reason in reasons
    )
    source_approved = (
        source.metadata_status is MetadataStatus.VERIFIED
        and source.ingestion_status is IngestionStatus.INGESTED
        and source.review_status is CurriculumReviewStatus.APPROVED
        and source.usage_rights_status is UsageRightsStatus.PERMITTED
        and all(
            (
                source.publisher_authority,
                source.source_location,
                source.source_version,
                source.grade,
                source.subject,
                source.language,
            )
        )
    )
    if not source_approved:
        reasons.append(IngestionValidationReason.SOURCE_NOT_APPROVED)
    if not reasons:
        reasons.append(IngestionValidationReason.READY)
    return IngestionValidationResult(
        extraction_usable=extraction_usable,
        eligible_for_approved_ingestion=extraction_usable and source_approved,
        reasons=tuple(reasons),
        source_id=page.source_id,
        page_number=page.page_number,
        content_sha256=hashlib.sha256(encoded).hexdigest() if encoded else None,
    )


def _looks_garbled(text: str) -> bool:
    if "\ufffd" in text:
        return True
    significant = [character for character in text if not character.isspace()]
    if not significant:
        return False
    invalid = sum(
        unicodedata.category(character) in {"Cc", "Cs", "Co", "Cn"} for character in significant
    )
    return invalid / len(significant) > 0.01


def _has_expected_script(text: str, language: str) -> bool:
    expected = _SCRIPTS.get(language)
    if expected is None:
        return False
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and any(
        any(script in unicodedata.name(character, "") for script in expected)
        for character in letters
    )
