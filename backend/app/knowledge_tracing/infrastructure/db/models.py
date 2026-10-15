from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base

# JSONB on PostgreSQL, plain JSON elsewhere (tests run on SQLite).
JsonType = JSON().with_variant(JSONB(), "postgresql")
# bigserial on PostgreSQL; SQLite only autoincrements INTEGER primary keys.
BigIntType = BigInteger().with_variant(Integer(), "sqlite")


class SkillModel(Base):
    """The 30 skills. `sort_index` is the model's skill index and must never be reordered."""

    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("sort_index BETWEEN 0 AND 29", name="ck_skills_sort_index"),
        CheckConstraint("area IN ('APT', 'MAT', 'LAN', 'ENV')", name="ck_skills_area"),
    )

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    sort_index: Mapped[int] = mapped_column(SmallInteger, unique=True)
    area: Mapped[str] = mapped_column(String(3))
    name_en: Mapped[str] = mapped_column(String(100))
    name_si: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class QuestionModel(Base):
    """One question of the bank. Language-independent facts; images and keys live in variants."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_questions_difficulty"),
        CheckConstraint(
            "difficulty_source IN ('manual', 'skill_default', 'measured')",
            name="ck_questions_difficulty_source",
        ),
        CheckConstraint("est_seconds > 0", name="ck_questions_est_seconds"),
        Index("ix_questions_skill_difficulty", "skill_code", "difficulty"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # bank id, e.g. '3.41'
    skill_code: Mapped[str] = mapped_column(ForeignKey("skills.code"))  # the first listed skill
    secondary_skill_codes: Mapped[list[str]] = mapped_column(
        JsonType, server_default=text("'[]'")
    )  # further skills of a multi-skill question; not used by the model
    difficulty: Mapped[str] = mapped_column(String(10))
    difficulty_source: Mapped[str] = mapped_column(String(15), server_default="manual")
    est_seconds: Mapped[int] = mapped_column(Integer, server_default=text("60"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QuestionVariantModel(Base):
    """The Sinhala or Tamil version of a question: its image and its raw answer key."""

    __tablename__ = "question_variants"
    __table_args__ = (
        CheckConstraint("language IN ('si', 'ta')", name="ck_question_variants_language"),
        CheckConstraint("image_width_px > 0", name="ck_question_variants_width"),
        CheckConstraint("image_height_px > 0", name="ck_question_variants_height"),
    )

    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(2), primary_key=True)
    image_key: Mapped[str] = mapped_column(String(255))  # storage key, never a URL
    image_width_px: Mapped[int] = mapped_column(Integer)
    image_height_px: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    answer_key_raw: Mapped[str] = mapped_column(Text)  # original key line, for traceability
    # True when the bank image already has its own answer space (dotted lines, option list).
    answer_space_in_image: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class QuestionPartModel(Base):
    """One answer of a question variant, in the order the child answers them."""

    __tablename__ = "question_parts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "language"],
            ["question_variants.question_id", "question_variants.language"],
            ondelete="CASCADE",
        ),
        CheckConstraint("part_no >= 1", name="ck_question_parts_part_no"),
        CheckConstraint("part_type IN ('mcq', 'short')", name="ck_question_parts_part_type"),
        CheckConstraint(
            "answer_kind IN ('choice', 'number', 'text', 'instruction')",
            name="ck_question_parts_answer_kind",
        ),
        CheckConstraint(
            "part_type <> 'mcq' OR (option_labels IS NOT NULL AND correct_option IS NOT NULL)",
            name="ck_question_parts_mcq_fields",
        ),
        CheckConstraint(
            "part_type <> 'short' OR instruction IS NOT NULL OR accepted_answers IS NOT NULL",
            name="ck_question_parts_short_fields",
        ),
    )

    question_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    language: Mapped[str] = mapped_column(String(2), primary_key=True)
    part_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    part_type: Mapped[str] = mapped_column(String(5))
    answer_kind: Mapped[str] = mapped_column(String(11), server_default="text")
    option_labels: Mapped[list[str] | None] = mapped_column(JsonType)
    correct_option: Mapped[str | None] = mapped_column(String(10))
    accepted_answers: Mapped[list[str] | None] = mapped_column(JsonType)
    instruction: Mapped[str | None] = mapped_column(Text)
    label_on_image: Mapped[str | None] = mapped_column(String(20))


class AttemptModel(Base):
    """One answered question by one learner, digital (source=1) or paper (source=0)."""

    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint("language IN ('si', 'ta')", name="ck_attempts_language"),
        CheckConstraint("source IN (0, 1)", name="ck_attempts_source"),
        CheckConstraint("penalty BETWEEN 0 AND 1", name="ck_attempts_penalty"),
        Index("ix_attempts_history", "learner_id", "answered_at", "id"),
        Index(
            "uq_attempts_paper_item",
            "paper_item_id",
            unique=True,
            postgresql_where=text("paper_item_id IS NOT NULL"),
            sqlite_where=text("paper_item_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    language: Mapped[str] = mapped_column(String(2))
    source: Mapped[int] = mapped_column(SmallInteger)  # 1 digital game, 0 paper
    correct: Mapped[bool] = mapped_column(Boolean)
    time_ms: Mapped[int | None] = mapped_column(Integer)  # digital only
    hints: Mapped[int | None] = mapped_column(Integer)  # digital only
    penalty: Mapped[float] = mapped_column(Float)  # computed by the backend
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paper_item_id: Mapped[UUID | None] = mapped_column(Uuid)  # set for paper attempts
    # Lets a repeated request return the same attempt instead of creating a duplicate.
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MasterySnapshotModel(Base):
    """One computed mastery vector for a learner. Snapshots are append-only history."""

    __tablename__ = "mastery_snapshots"
    __table_args__ = (
        CheckConstraint("n_attempts >= 0", name="ck_mastery_snapshots_n_attempts"),
        Index("ix_mastery_snapshots_latest", "learner_id", "computed_at"),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(String(40))
    n_attempts: Mapped[int] = mapped_column(Integer)  # the learner's total attempts at that time
    # [{"code": "MAT-FRC", "mastery": 0.62, "attempts": 14}, ...] in model skill order
    skills: Mapped[list[dict]] = mapped_column(JsonType)


PAPER_STATUSES = ("generated", "partially_uploaded", "graded", "needs_review", "confirmed", "cancelled")


class PaperModel(Base):
    """One generated practice paper (a PDF of 1 to 3 pages) for one learner and one week."""

    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('generated', 'partially_uploaded', 'graded', 'needs_review', "
            "'confirmed', 'cancelled')",
            name="ck_papers_status",
        ),
        CheckConstraint("mode IN ('practice', 'diagnostic')", name="ck_papers_mode"),
        CheckConstraint("language IN ('si', 'ta')", name="ck_papers_language"),
        CheckConstraint("page_count BETWEEN 1 AND 6", name="ck_papers_page_count"),
        Index("ix_papers_learner", "learner_id", "week_start"),
        # One live paper per learner per week; a cancelled paper frees the week again.
        Index(
            "uq_papers_learner_week",
            "learner_id",
            "week_start",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"))
    # Opaque code printed on every page (12 base32 characters); carries nothing about the child.
    qr_token: Mapped[str] = mapped_column(String(16), unique=True)
    week_start: Mapped[date] = mapped_column(Date)  # the Monday of the paper's week
    status: Mapped[str] = mapped_column(String(20), server_default="generated")
    mode: Mapped[str] = mapped_column(String(10))
    language: Mapped[str] = mapped_column(String(2))
    params: Mapped[dict] = mapped_column(JsonType)  # request, selection summary, dropped questions
    mastery_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("mastery_snapshots.id"))
    model_version: Mapped[str] = mapped_column(String(40))
    page_count: Mapped[int] = mapped_column(SmallInteger)
    pdf_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PaperItemModel(Base):
    """One question at one position on a paper, with where it sits on the page."""

    __tablename__ = "paper_items"
    __table_args__ = (
        UniqueConstraint("paper_id", "position", name="uq_paper_items_position"),
        CheckConstraint("page >= 1", name="ck_paper_items_page"),
        CheckConstraint(
            "block_x BETWEEN 0 AND 1 AND block_y BETWEEN 0 AND 1 "
            "AND block_w > 0 AND block_h > 0",
            name="ck_paper_items_block",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)  # the printed question number, 1-based
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    language: Mapped[str] = mapped_column(String(2))
    page: Mapped[int] = mapped_column(SmallInteger)  # 1-based
    # The whole question block as fractions (0..1) of the frame between the 4 marker centres.
    block_x: Mapped[float] = mapped_column(Float)
    block_y: Mapped[float] = mapped_column(Float)
    block_w: Mapped[float] = mapped_column(Float)
    block_h: Mapped[float] = mapped_column(Float)
    # Optional extra answer boxes; null when the question image already holds its answer space.
    answer_boxes: Mapped[list[dict] | None] = mapped_column(JsonType)
    shown_difficulty: Mapped[str] = mapped_column(String(10))
    role: Mapped[str] = mapped_column(String(12))  # weak | strong | verify | unknown | diagnostic
    predicted_p: Mapped[float | None] = mapped_column(Float)  # model's P(correct) when selected


class VisionCallModel(Base):
    """One HTTP attempt to a reader: cost, speed and quota monitoring.

    Holds no picture and no transcription of handwriting, only timings, token counts and an
    error code.
    """

    __tablename__ = "vision_calls"
    __table_args__ = (
        CheckConstraint("role IN ('primary', 'second_opinion')", name="ck_vision_calls_role"),
        Index("ix_vision_calls_day", "provider", "model", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    # The submission table comes with the upload step; until then this is a plain identifier.
    submission_id: Mapped[UUID | None] = mapped_column(Uuid)
    paper_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_items.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(16), server_default="primary")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


SUBMISSION_STATUSES = (
    "uploaded",  # stored, waiting to be graded
    "grading",  # being straightened, read and marked
    "failed_alignment",  # the photo cannot be used: the parent retakes it
    "graded",  # every answer on the page was decided without the parent
    "needs_review",  # some answers wait for the parent
    "confirmed",  # the parent decided the unclear answers
    "error",  # something went wrong on our side
)


class PaperSubmissionModel(Base):
    """One uploaded photo of one page of a paper."""

    __tablename__ = "paper_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'grading', 'failed_alignment', 'graded', 'needs_review', "
            "'confirmed', 'error')",
            name="ck_paper_submissions_status",
        ),
        CheckConstraint("page >= 1", name="ck_paper_submissions_page"),
        Index(
            "uq_paper_submissions_current",
            "paper_id",
            "page",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id"))
    page: Mapped[int] = mapped_column(SmallInteger)
    image_key: Mapped[str] = mapped_column(String(255))  # the original photo, private
    status: Mapped[str] = mapped_column(String(20), server_default="uploaded")
    failure_reason: Mapped[str | None] = mapped_column(String(40))
    alignment_info: Mapped[dict | None] = mapped_column(JsonType)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The first time the parent saw this page in a result report: its photos then have 7 days.
    report_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the photo and the crops were removed from storage (retention).
    files_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GradedAnswerModel(Base):
    """The reading and the marking of one part of one question on one submission."""

    __tablename__ = "graded_answers"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "paper_item_id", "part_no", name="uq_graded_answers_part"
        ),
        CheckConstraint(
            "auto_status IN ('correct', 'wrong', 'blank', 'ambiguous')",
            name="ck_graded_answers_auto_status",
        ),
        CheckConstraint(
            "final_status IS NULL OR final_status IN ('correct', 'wrong', 'blank')",
            name="ck_graded_answers_final_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_submissions.id", ondelete="CASCADE")
    )
    paper_item_id: Mapped[UUID] = mapped_column(ForeignKey("paper_items.id"))
    part_no: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    crop_key: Mapped[str | None] = mapped_column(String(255))  # the picture the reader saw
    vision_provider: Mapped[str] = mapped_column(String(20))
    vision_model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(30))
    raw_response: Mapped[dict | None] = mapped_column(JsonType)  # the reading; never the key
    match_how: Mapped[str | None] = mapped_column(String(120))
    instruction_met: Mapped[bool | None] = mapped_column(Boolean)
    read_selected: Mapped[str | None] = mapped_column(String(40))  # a choice part: the label
    read_text: Mapped[str | None] = mapped_column(Text)  # a short part: what was written
    auto_status: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    review_reason: Mapped[str | None] = mapped_column(String(40))
    final_status: Mapped[str | None] = mapped_column(String(10))  # null until decided
    confirmed_by: Mapped[str | None] = mapped_column(String(64))  # "auto" or the parent
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
