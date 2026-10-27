"""Create initial PortfolioVN tables.

Revision ID: 0001_initial_schema
Revises:
"""
from __future__ import annotations

from alembic import op
from app.models import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # This removes all pvn_* application tables. Do not run on a shared DB without a backup.
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
