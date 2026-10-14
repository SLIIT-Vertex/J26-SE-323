from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
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
