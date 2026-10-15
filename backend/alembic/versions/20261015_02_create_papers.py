"""Store the weekly practice papers and where every question sits on its pages."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261015_02"
down_revision: str | None = "20261015_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("qr_token", sa.String(length=16), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="generated", nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("params", json_type, nullable=False),
        sa.Column("mastery_snapshot_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite")),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("page_count", sa.SmallInteger(), nullable=False),
        sa.Column("pdf_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('generated', 'partially_uploaded', 'graded', 'needs_review', "
            "'confirmed', 'cancelled')",
            name="ck_papers_status",
        ),
        sa.CheckConstraint("mode IN ('practice', 'diagnostic')", name="ck_papers_mode"),
        sa.CheckConstraint("language IN ('si', 'ta')", name="ck_papers_language"),
        sa.CheckConstraint("page_count BETWEEN 1 AND 6", name="ck_papers_page_count"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.ForeignKeyConstraint(["mastery_snapshot_id"], ["mastery_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qr_token"),
    )
    op.create_index("ix_papers_learner", "papers", ["learner_id", "week_start"])
    op.create_index(
        "uq_papers_learner_week",
        "papers",
        ["learner_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )

    op.create_table(
        "paper_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("question_id", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("page", sa.SmallInteger(), nullable=False),
        sa.Column("block_x", sa.Float(), nullable=False),
        sa.Column("block_y", sa.Float(), nullable=False),
        sa.Column("block_w", sa.Float(), nullable=False),
        sa.Column("block_h", sa.Float(), nullable=False),
        sa.Column("answer_boxes", json_type, nullable=True),
        sa.Column("shown_difficulty", sa.String(length=10), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("predicted_p", sa.Float(), nullable=True),
        sa.CheckConstraint("page >= 1", name="ck_paper_items_page"),
        sa.CheckConstraint(
            "block_x BETWEEN 0 AND 1 AND block_y BETWEEN 0 AND 1 "
            "AND block_w > 0 AND block_h > 0",
            name="ck_paper_items_block",
        ),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "position", name="uq_paper_items_position"),
    )


def downgrade() -> None:
    op.drop_table("paper_items")
    op.drop_table("papers")
