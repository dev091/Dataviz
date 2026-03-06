"""organization subscription scaffold

Revision ID: 202603060002
Revises: 202603060001
Create Date: 2026-03-06 01:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202603060002"
down_revision: str | None = "202603060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("plan_tier", sa.String(length=32), nullable=False, server_default=sa.text("'starter'")))
    op.add_column("organizations", sa.Column("subscription_status", sa.String(length=32), nullable=False, server_default=sa.text("'trial'")))
    op.add_column("organizations", sa.Column("billing_email", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("seat_limit", sa.Integer(), nullable=False, server_default=sa.text("10")))
    op.add_column("organizations", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("organizations", "seat_limit")
    op.drop_column("organizations", "billing_email")
    op.drop_column("organizations", "subscription_status")
    op.drop_column("organizations", "plan_tier")
