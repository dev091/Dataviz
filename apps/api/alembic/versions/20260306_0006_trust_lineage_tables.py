"""add trust and lineage tables

Revision ID: 202603060006
Revises: 202603060005
Create Date: 2026-03-06 23:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202603060006"
down_revision: str | None = "202603060005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "metric_lineage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_model_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_metric_id", sa.String(length=36), nullable=False),
        sa.Column("source_dataset_id", sa.String(length=36), nullable=False),
        sa.Column("source_field", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("transformation_summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["semantic_model_id"], ["semantic_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["semantic_metric_id"], ["semantic_metrics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transformation_lineage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("input_fields", json_type, nullable=False),
        sa.Column("output_fields", json_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'applied'")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ai_action_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=False),
        sa.Column("artifact_ref", sa.String(length=36), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'completed'")),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_action_history_action_type", "ai_action_history", ["action_type"], unique=False)

    op.create_table(
        "artifact_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifact_feedback_artifact_type", "artifact_feedback", ["artifact_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_artifact_feedback_artifact_type", table_name="artifact_feedback")
    op.drop_table("artifact_feedback")
    op.drop_index("ix_ai_action_history_action_type", table_name="ai_action_history")
    op.drop_table("ai_action_history")
    op.drop_table("transformation_lineage")
    op.drop_table("metric_lineage")
