from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# A submission is final once every answer on its page was decided.
FINAL_STATUSES = ("graded", "confirmed")
# While in these, the app keeps asking for news.
IN_PROGRESS_STATUSES = ("uploaded", "grading")


@dataclass(frozen=True, slots=True)
class Submission:
    id: UUID
    paper_id: UUID
    page: int
    image_key: str
    status: str
    failure_reason: str | None
    alignment_info: dict | None
    is_current: bool
    uploaded_at: datetime
    report_viewed_at: datetime | None = None
    files_deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GradedPart:
    """One part of one question on a submission: what was read and how it was marked."""

    id: UUID
    submission_id: UUID
    paper_item_id: UUID
    part_no: int
    crop_key: str | None
    vision_provider: str
    vision_model: str
    prompt_version: str
    raw_response: dict | None
    match_how: str | None
    instruction_met: bool | None
    read_selected: str | None
    read_text: str | None
    auto_status: str  # correct | wrong | blank | ambiguous
    confidence: float | None
    needs_review: bool
    review_reason: str | None
    final_status: str | None  # correct | wrong | blank, or None until decided
    confirmed_by: str | None

    @property
    def is_final(self) -> bool:
        return self.final_status is not None
