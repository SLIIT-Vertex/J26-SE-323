"""Add the games' help-order bandit: its learned state, decision snapshots and ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "gam_20261118_01"
down_revision: str | None = "gam_20261022_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "game_help_bandit_states",
        sa.Column(
            "model_version_id", sa.Uuid(), sa.ForeignKey("model_versions.id"), primary_key=True
        ),
        sa.Column("subject", sa.String(8), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("ledger_position", sa.Integer(), nullable=False),
        sa.Column("parameters_json", JSON, nullable=False),
        sa.Column("parameters_sha256", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ledger_position >= 0", name="ck_game_help_bandit_states_position"),
        sa.CheckConstraint(
            "length(artifact_sha256) = 64", name="ck_game_help_bandit_states_artifact"
        ),
        sa.CheckConstraint(
            "length(parameters_sha256) = 64", name="ck_game_help_bandit_states_parameters"
        ),
    )
    op.create_index("ix_game_help_bandit_states_subject", "game_help_bandit_states", ["subject"])
    op.create_table(
        "game_help_bandit_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey("learning_flow_episode_runs.episode_id"),
            nullable=False,
        ),
        sa.Column(
            "model_version_id", sa.Uuid(), sa.ForeignKey("model_versions.id"), nullable=False
        ),
        sa.Column("subject", sa.String(8), nullable=False),
        sa.Column("context_version", sa.String(64), nullable=False),
        sa.Column("snapshot_json", JSON, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("episode_id", name="uq_game_help_bandit_snapshots_episode"),
        sa.CheckConstraint(
            "length(snapshot_sha256) = 64", name="ck_game_help_bandit_snapshots_sha256"
        ),
    )
    op.create_table(
        "game_help_bandit_ledger",
        sa.Column(
            "model_version_id", sa.Uuid(), sa.ForeignKey("model_versions.id"), primary_key=True
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey("learning_flow_episode_runs.episode_id"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("game_help_bandit_snapshots.snapshot_id"),
            nullable=False,
        ),
        sa.Column("help_type", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("credit_rule_version", sa.String(64), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "model_version_id",
            "episode_id",
            "help_type",
            name="uq_game_help_bandit_ledger_episode_help",
        ),
        sa.CheckConstraint("position >= 1", name="ck_game_help_bandit_ledger_position"),
        sa.CheckConstraint(
            "role IN ('credited', 'failed_round')", name="ck_game_help_bandit_ledger_role"
        ),
        sa.CheckConstraint("weight >= 0", name="ck_game_help_bandit_ledger_weight"),
    )
    op.create_index("ix_game_help_bandit_ledger_episode", "game_help_bandit_ledger", ["episode_id"])


def downgrade() -> None:
    op.drop_index("ix_game_help_bandit_ledger_episode", table_name="game_help_bandit_ledger")
    op.drop_table("game_help_bandit_ledger")
    op.drop_table("game_help_bandit_snapshots")
    op.drop_index("ix_game_help_bandit_states_subject", table_name="game_help_bandit_states")
    op.drop_table("game_help_bandit_states")
