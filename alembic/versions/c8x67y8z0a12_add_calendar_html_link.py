"""Add html_link column to calendar_events table

Revision ID: c8x67y8z0a12
Revises: b7w56x7y9z01
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8x67y8z0a12'
down_revision = 'b7w56x7y9z01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add html_link column to store Google Calendar direct link
    op.add_column(
        'calendar_events',
        sa.Column(
            'html_link',
            sa.String(500),
            nullable=True,
            comment='Direct link to view event in Google Calendar'
        )
    )


def downgrade() -> None:
    op.drop_column('calendar_events', 'html_link')
