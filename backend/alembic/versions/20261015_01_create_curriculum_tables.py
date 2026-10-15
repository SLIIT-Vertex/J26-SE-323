"""Create the shared curriculum index tables.

This revision is the curriculum branch root. It is not part of the gamification chain.
`vector(384)` matches intfloat/multilingual-e5-small. SQLite tests store that column as JSON.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261015_01"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = ("curriculum",)
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "curriculum_sources",
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher_authority", sa.String(length=512), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("subject", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_location", sa.String(length=512), nullable=True),
        sa.Column("source_version", sa.String(length=128), nullable=True),
        sa.Column("source_document_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_status", sa.String(length=32), nullable=False),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("usage_rights_status", sa.String(length=32), nullable=False),
        sa.CheckConstraint("grade IS NULL OR grade IN (4, 5)", name="ck_curriculum_sources_grade"),
        sa.CheckConstraint(
            "metadata_status IN ('VERIFIED', 'PROVISIONAL', 'UNKNOWN')",
            name="ck_curriculum_sources_metadata_status",
        ),
        sa.CheckConstraint(
            "ingestion_status IN ('NOT_INGESTED', 'READY', 'INGESTED', 'FAILED')",
            name="ck_curriculum_sources_ingestion_status",
        ),
        sa.CheckConstraint(
            "review_status IN ('UNREVIEWED', 'REVIEW_PENDING', 'APPROVED', 'REJECTED')",
            name="ck_curriculum_sources_review_status",
        ),
        sa.CheckConstraint(
            "usage_rights_status IN ('UNKNOWN', 'PERMITTED', 'RESTRICTED')",
            name="ck_curriculum_sources_usage_rights",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_table(
        "curriculum_chunks",
        sa.Column("chunk_id", sa.String(length=256), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_version", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("subject", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("skill_ids", json_type, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_locator", sa.String(length=512), nullable=True),
        sa.Column("unit_id", sa.String(length=128), nullable=True),
        sa.Column("learning_outcome_id", sa.String(length=128), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("chunking_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint("grade IN (4, 5)", name="ck_curriculum_chunks_grade"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1", name="ck_curriculum_chunks_page"
        ),
        sa.CheckConstraint(
            "review_status IN ('UNREVIEWED', 'REVIEW_PENDING', 'APPROVED', 'REJECTED')",
            name="ck_curriculum_chunks_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["curriculum_sources.source_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index("ix_curriculum_chunks_source_id", "curriculum_chunks", ["source_id"])
    op.create_index(
        "ix_curriculum_chunks_filter",
        "curriculum_chunks",
        ["grade", "subject", "language", "review_status"],
    )
    _create_embedding_table()


def downgrade() -> None:
    op.drop_index("ix_curriculum_chunks_filter", table_name="curriculum_chunks")
    op.drop_index("ix_curriculum_chunks_source_id", table_name="curriculum_chunks")
    op.drop_table("curriculum_chunk_embeddings")
    op.drop_table("curriculum_chunks")
    op.drop_table("curriculum_sources")


def _create_embedding_table() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE TABLE curriculum_chunk_embeddings (
                chunk_id VARCHAR(256) NOT NULL,
                model_name VARCHAR(256) NOT NULL,
                model_revision VARCHAR(128) NOT NULL,
                vector vector(384) NOT NULL,
                PRIMARY KEY (chunk_id, model_name, model_revision),
                FOREIGN KEY (chunk_id)
                    REFERENCES curriculum_chunks (chunk_id) ON DELETE CASCADE
            )
            """
        )
        return
    op.create_table(
        "curriculum_chunk_embeddings",
        sa.Column("chunk_id", sa.String(length=256), nullable=False),
        sa.Column("model_name", sa.String(length=256), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["curriculum_chunks.chunk_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id", "model_name", "model_revision"),
    )
