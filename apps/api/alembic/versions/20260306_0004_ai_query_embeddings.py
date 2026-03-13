"""add ai query embeddings

Revision ID: 202603060004
Revises: 202603060003
Create Date: 2026-03-06 18:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "202603060004"
down_revision: str | None = "202603060003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column("ai_query_sessions", sa.Column("question_embedding", Vector(16), nullable=True))
        return

    op.add_column("ai_query_sessions", sa.Column("question_embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_query_sessions", "question_embedding")
