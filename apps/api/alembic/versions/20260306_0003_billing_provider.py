"""billing provider integration scaffold

Revision ID: 202603060003
Revises: 202603060002
Create Date: 2026-03-06 19:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202603060003"
down_revision: str | None = "202603060002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("billing_provider", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
    )
    op.add_column("organizations", sa.Column("billing_customer_id", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("billing_subscription_id", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("billing_price_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "billing_price_id")
    op.drop_column("organizations", "billing_subscription_id")
    op.drop_column("organizations", "billing_customer_id")
    op.drop_column("organizations", "billing_provider")
