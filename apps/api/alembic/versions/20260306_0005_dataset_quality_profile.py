"""add dataset quality profile

Revision ID: 202603060005
Revises: 202603060004
Create Date: 2026-03-06 23:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202603060005"
down_revision: str | None = "202603060004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("quality_status", sa.String(length=32), nullable=False, server_default="unknown"))
    op.add_column("datasets", sa.Column("quality_profile", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    op.execute("UPDATE datasets SET quality_status = 'unknown' WHERE quality_status IS NULL")
    op.execute("UPDATE datasets SET quality_profile = '{}' WHERE quality_profile IS NULL")

    with op.batch_alter_table("datasets") as batch_op:
        batch_op.alter_column("quality_status", server_default=None)
        batch_op.alter_column("quality_profile", server_default=None)


def downgrade() -> None:
    op.drop_column("datasets", "quality_profile")
    op.drop_column("datasets", "quality_status")
