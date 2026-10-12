"""Create the knowledge tracing tables: skills, questions, variants, parts and attempts."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261013_01"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
big_int = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("sort_index", sa.SmallInteger(), nullable=False),
        sa.Column("area", sa.String(length=3), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column("name_si", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("sort_index BETWEEN 0 AND 29", name="ck_skills_sort_index"),
        sa.CheckConstraint("area IN ('APT', 'MAT', 'LAN', 'ENV')", name="ck_skills_area"),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("sort_index"),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("skill_code", sa.String(length=16), nullable=False),
        sa.Column("secondary_skill_codes", json_type, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("difficulty_source", sa.String(length=15), server_default="manual", nullable=False),
        sa.Column("est_seconds", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("key_verified_by", sa.String(length=100), nullable=True),
        sa.Column("key_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')", name="ck_questions_difficulty"
        ),
        sa.CheckConstraint(
            "difficulty_source IN ('manual', 'skill_default', 'measured')",
            name="ck_questions_difficulty_source",
        ),
        sa.CheckConstraint("est_seconds > 0", name="ck_questions_est_seconds"),
        sa.ForeignKeyConstraint(["skill_code"], ["skills.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_questions_skill_difficulty", "questions", ["skill_code", "difficulty"]
    )

    op.create_table(
        "question_variants",
        sa.Column("question_id", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("image_key", sa.String(length=255), nullable=False),
        sa.Column("image_width_px", sa.Integer(), nullable=False),
        sa.Column("image_height_px", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("answer_key_raw", sa.Text(), nullable=False),
        sa.Column(
            "answer_space_in_image", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint("language IN ('si', 'ta')", name="ck_question_variants_language"),
        sa.CheckConstraint("image_width_px > 0", name="ck_question_variants_width"),
        sa.CheckConstraint("image_height_px > 0", name="ck_question_variants_height"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("question_id", "language"),
        sa.UniqueConstraint("content_hash"),
    )

    op.create_table(
        "question_parts",
        sa.Column("question_id", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("part_no", sa.SmallInteger(), nullable=False),
        sa.Column("part_type", sa.String(length=5), nullable=False),
        sa.Column("answer_kind", sa.String(length=11), server_default="text", nullable=False),
        sa.Column("option_labels", json_type, nullable=True),
        sa.Column("correct_option", sa.String(length=10), nullable=True),
        sa.Column("accepted_answers", json_type, nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("label_on_image", sa.String(length=20), nullable=True),
        sa.CheckConstraint("part_no >= 1", name="ck_question_parts_part_no"),
        sa.CheckConstraint("part_type IN ('mcq', 'short')", name="ck_question_parts_part_type"),
        sa.CheckConstraint(
            "answer_kind IN ('choice', 'number', 'text', 'instruction')",
            name="ck_question_parts_answer_kind",
        ),
        sa.CheckConstraint(
            "part_type <> 'mcq' OR (option_labels IS NOT NULL AND correct_option IS NOT NULL)",
            name="ck_question_parts_mcq_fields",
        ),
        sa.CheckConstraint(
            "part_type <> 'short' OR instruction IS NOT NULL OR accepted_answers IS NOT NULL",
            name="ck_question_parts_short_fields",
        ),
        sa.ForeignKeyConstraint(
            ["question_id", "language"],
            ["question_variants.question_id", "question_variants.language"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "language", "part_no"),
    )

    op.create_table(
        "attempts",
        sa.Column("id", big_int, autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("source", sa.SmallInteger(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=True),
        sa.Column("hints", sa.Integer(), nullable=True),
        sa.Column("penalty", sa.Float(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paper_item_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("language IN ('si', 'ta')", name="ck_attempts_language"),
        sa.CheckConstraint("source IN (0, 1)", name="ck_attempts_source"),
        sa.CheckConstraint("penalty BETWEEN 0 AND 1", name="ck_attempts_penalty"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attempts_history", "attempts", ["learner_id", "answered_at", "id"])
    op.create_index(
        "uq_attempts_paper_item",
        "attempts",
        ["paper_item_id"],
        unique=True,
        postgresql_where=sa.text("paper_item_id IS NOT NULL"),
        sqlite_where=sa.text("paper_item_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("question_parts")
    op.drop_table("question_variants")
    op.drop_index("ix_questions_skill_difficulty", table_name="questions")
    op.drop_table("questions")
    op.drop_table("skills")
