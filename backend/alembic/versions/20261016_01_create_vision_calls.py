"""Record every call to the vision reader (cost, speed, quota), without any picture or text."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_01"
down_revision: str | None = "20261015_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

big_int = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "vision_calls",
        sa.Column("id", big_int, autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=True),
        sa.Column("paper_item_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="primary", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('primary', 'second_opinion')", name="ck_vision_calls_role"),
        sa.ForeignKeyConstraint(["paper_item_id"], ["paper_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vision_calls_day", "vision_calls", ["provider", "model", "created_at"])


def downgrade() -> None:
    op.drop_table("vision_calls")
