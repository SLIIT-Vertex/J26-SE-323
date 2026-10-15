"""Store uploaded page photos and the marking of every part on them."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261017_01"
down_revision: str | None = "20261016_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "paper_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.SmallInteger(), nullable=False),
        sa.Column("image_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="uploaded", nullable=False),
        sa.Column("failure_reason", sa.String(length=40), nullable=True),
        sa.Column("alignment_info", json_type, nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('uploaded', 'grading', 'failed_alignment', 'graded', 'needs_review', "
            "'confirmed', 'error')",
            name="ck_paper_submissions_status",
        ),
        sa.CheckConstraint("page >= 1", name="ck_paper_submissions_page"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_paper_submissions_current",
        "paper_submissions",
        ["paper_id", "page"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )

    op.create_table(
        "graded_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("paper_item_id", sa.Uuid(), nullable=False),
        sa.Column("part_no", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("crop_key", sa.String(length=255), nullable=True),
        sa.Column("vision_provider", sa.String(length=20), nullable=False),
        sa.Column("vision_model", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("raw_response", json_type, nullable=True),
        sa.Column("match_how", sa.String(length=120), nullable=True),
        sa.Column("instruction_met", sa.Boolean(), nullable=True),
        sa.Column("read_selected", sa.String(length=40), nullable=True),
        sa.Column("read_text", sa.Text(), nullable=True),
        sa.Column("auto_status", sa.String(length=10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("review_reason", sa.String(length=40), nullable=True),
        sa.Column("final_status", sa.String(length=10), nullable=True),
        sa.Column("confirmed_by", sa.String(length=64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "auto_status IN ('correct', 'wrong', 'blank', 'ambiguous')",
            name="ck_graded_answers_auto_status",
        ),
        sa.CheckConstraint(
            "final_status IS NULL OR final_status IN ('correct', 'wrong', 'blank')",
            name="ck_graded_answers_final_status",
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["paper_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_item_id"], ["paper_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id", "paper_item_id", "part_no", name="uq_graded_answers_part"
        ),
    )


def downgrade() -> None:
    op.drop_table("graded_answers")
    op.drop_table("paper_submissions")
