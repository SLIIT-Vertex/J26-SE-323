"""Add immutable Model 2 contexts, decisions, candidates, and reward links."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_05"
down_revision: str | None = "20261015_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model2_context_snapshots_v5",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(128), nullable=False),
        sa.Column("skill_version", sa.String(128), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(128), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("missingness_json", sa.JSON(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("belief_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("belief_model_version", sa.String(128), nullable=True),
        sa.Column("belief_mapping_version", sa.String(128), nullable=True),
        sa.Column("belief_artifact_sha256", sa.String(64), nullable=True),
        sa.Column("optional_freshness_json", sa.JSON(), nullable=False),
        sa.Column("feature_definitions_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("experiment_mode", sa.String(20), nullable=False),
        sa.Column("protocol_version", sa.String(128), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_model2_context_v5_hash"),
        sa.CheckConstraint(
            "experiment_mode IN ('baseline', 'proposed')", name="ck_model2_context_v5_experiment"
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["belief_snapshot_id"], ["model1_belief_snapshots_v4.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_sha256", name="uq_model2_context_v5_hash"),
    )
    op.create_index(
        "ix_model2_context_v5_learner_time",
        "model2_context_snapshots_v5",
        ["learner_id", "decision_at"],
    )
    op.create_table(
        "model2_scaffold_decisions_v5",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(128), nullable=False),
        sa.Column("experiment_mode", sa.String(20), nullable=False),
        sa.Column("context_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("context_schema_version", sa.String(128), nullable=False),
        sa.Column("selected_scaffold_id", sa.String(128), nullable=True),
        sa.Column("shadow_scaffold_id", sa.String(128), nullable=True),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("artifact_version", sa.String(128), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("selection_kind", sa.String(32), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("assignment_token", sa.String(128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("decision_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(artifact_sha256) = 64", name="ck_model2_decision_v5_artifact"),
        sa.CheckConstraint("length(decision_sha256) = 64", name="ck_model2_decision_v5_hash"),
        sa.CheckConstraint(
            "experiment_mode IN ('baseline', 'proposed')", name="ck_model2_decision_v5_experiment"
        ),
        sa.CheckConstraint(
            "mode IN ('deterministic_baseline', 'proposed_shadow', 'proposed_offline', 'learned_delivery', 'safe_fallback')",
            name="ck_model2_decision_v5_mode",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["context_snapshot_id"], ["model2_context_snapshots_v5.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_model2_decision_v5_episode"),
        sa.UniqueConstraint("decision_sha256", name="uq_model2_decision_v5_hash"),
    )
    op.create_table(
        "model2_candidate_decisions_v5",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("scaffold_id", sa.String(128), nullable=False),
        sa.Column("candidate_order", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.String(128), nullable=False),
        sa.Column("scaffold_type", sa.String(64), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("predicted_raw_ig", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("propensity", sa.Float(), nullable=False),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("context_schema_version", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "propensity >= 0 AND propensity <= 1", name="ck_model2_candidate_v5_propensity"
        ),
        sa.CheckConstraint(
            "scaffold_type IN ('visual_guidance', 'worked_parallel_example', 'step_by_step_guidance')",
            name="ck_model2_candidate_v5_action",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["model2_scaffold_decisions_v5.id"]),
        sa.PrimaryKeyConstraint("decision_id", "scaffold_id"),
    )
    op.create_table(
        "model2_reward_links_v5",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_id", sa.Uuid(), nullable=False),
        sa.Column("raw_independence_gain", sa.Numeric(8, 6), nullable=False),
        sa.Column("formula_version", sa.String(128), nullable=False),
        sa.Column("link_version", sa.String(128), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "raw_independence_gain >= -1 AND raw_independence_gain <= 1",
            name="ck_model2_reward_v5_raw_ig",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["model2_scaffold_decisions_v5.id"]),
        sa.ForeignKeyConstraint(["measurement_id"], ["independence_measurements_v3.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", name="uq_model2_reward_v5_decision"),
        sa.UniqueConstraint("measurement_id", name="uq_model2_reward_v5_measurement"),
    )


def downgrade() -> None:
    op.drop_table("model2_reward_links_v5")
    op.drop_table("model2_candidate_decisions_v5")
    op.drop_table("model2_scaffold_decisions_v5")
    op.drop_index("ix_model2_context_v5_learner_time", table_name="model2_context_snapshots_v5")
    op.drop_table("model2_context_snapshots_v5")
