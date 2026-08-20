"""Widen agent_runs.correlation_id for Teams conversation ids.

Revision ID: 20260818_widen_corr_id
Revises: 20260715_drop_visitor_playground
Create Date: 2026-08-18

Note: revision id is intentionally shorter than the filename. alembic_version.version_num
is varchar(32); the longer id "20260818_widen_agent_run_correlation_id" (42 chars)
overflows it (live gidev upgrade hit StringDataRightTruncation on the bookkeeping
UPDATE; the ALTER COLUMN rolled back with transactional DDL).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260818_widen_corr_id"
down_revision = "20260715_drop_visitor_playground"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "agent_runs",
        "correlation_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "agent_runs",
        "correlation_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
