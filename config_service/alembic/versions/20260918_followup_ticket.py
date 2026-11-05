"""Add ticket_key / ticket_provider to investigation_followups.

Revision ID: 20260918_followup_ticket
Revises: 20260916_inv_followups
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20260918_followup_ticket"
down_revision = "20260916_inv_followups"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "investigation_followups",
        sa.Column("ticket_key", sa.String(64), nullable=True),
    )
    op.add_column(
        "investigation_followups",
        sa.Column("ticket_provider", sa.String(32), nullable=True),
    )


def downgrade():
    op.drop_column("investigation_followups", "ticket_provider")
    op.drop_column("investigation_followups", "ticket_key")
