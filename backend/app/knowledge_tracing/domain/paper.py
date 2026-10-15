from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Paper:
    id: UUID
    learner_id: UUID
    token: str
    week_start: date
    status: str
    mode: str
    language: str
    params: dict
    mastery_snapshot_id: int | None
    model_version: str
    page_count: int
    pdf_key: str
    created_at: datetime | None = None

    @property
    def question_count(self) -> int:
        return int(self.params.get("question_count", 0))

    @property
    def estimated_minutes(self) -> float:
        return float(self.params.get("estimated_minutes", 0.0))


@dataclass(frozen=True, slots=True)
class PaperItem:
    id: UUID
    paper_id: UUID
    position: int
    question_id: str
    skill_code: str
    language: str
    page: int
    block_x: float
    block_y: float
    block_w: float
    block_h: float
    shown_difficulty: str
    role: str
    predicted_p: float | None
    answer_boxes: list[dict] | None = None
