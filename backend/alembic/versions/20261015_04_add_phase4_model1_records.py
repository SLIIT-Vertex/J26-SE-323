"""Add append-only Model 1 feature and belief snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_04"
down_revision: str | None = "20261015_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model1_feature_snapshots_v4",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(128), nullable=False),
        sa.Column("skill_version", sa.String(128), nullable=False),
        sa.Column("item_revision_id", sa.String(128), nullable=False),
        sa.Column("inference_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_window_version", sa.String(128), nullable=False),
        sa.Column("feature_schema_version", sa.String(128), nullable=False),
        sa.Column("mapping_version", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("missingness_json", sa.JSON(), nullable=False),
        sa.Column("optional_freshness_json", sa.JSON(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("evidence_event_ids_json", sa.JSON(), nullable=False),
        sa.Column("attempt_ids_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_model1_features_v4_hash"),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_sha256", name="uq_model1_features_v4_hash"),
    )
    op.create_index("ix_model1_features_v4_learner_time", "model1_feature_snapshots_v4", ["learner_id", "inference_at"])
    op.create_table(
        "model1_belief_snapshots_v4",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feature_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("probabilities_json", sa.JSON(), nullable=False),
        sa.Column("top_hypothesis", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("entropy", sa.Float(), nullable=False),
        sa.Column("abstained", sa.Boolean(), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
        sa.Column("narrow_exploitation_allowed", sa.Boolean(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("feature_schema_version", sa.String(128), nullable=False),
        sa.Column("mapping_version", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("inference_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_model1_beliefs_v4_confidence"),
        sa.CheckConstraint("entropy >= 0", name="ck_model1_beliefs_v4_entropy"),
        sa.CheckConstraint("length(artifact_sha256) = 64", name="ck_model1_beliefs_v4_artifact_hash"),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_model1_beliefs_v4_snapshot_hash"),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], ["model1_feature_snapshots_v4.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_snapshot_id", "model_version", "artifact_sha256", name="uq_model1_beliefs_v4_replay"),
    )
    op.create_table(
        "model1_belief_probabilities_v4",
        sa.Column("belief_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("misconception_code", sa.String(128), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.CheckConstraint("probability >= 0 AND probability <= 1", name="ck_model1_probability_v4_range"),
        sa.CheckConstraint("misconception_code IN ('whole_set_as_half', 'subtracts_two', 'unknown_or_other')", name="ck_model1_probability_v4_catalogue"),
        sa.ForeignKeyConstraint(["belief_snapshot_id"], ["model1_belief_snapshots_v4.id"]),
        sa.PrimaryKeyConstraint("belief_snapshot_id", "misconception_code"),
    )


def downgrade() -> None:
    op.drop_table("model1_belief_probabilities_v4")
    op.drop_table("model1_belief_snapshots_v4")
    op.drop_index("ix_model1_features_v4_learner_time", table_name="model1_feature_snapshots_v4")
    op.drop_table("model1_feature_snapshots_v4")
