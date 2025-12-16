"""add_calendar_event_id_to_interactions

Revision ID: j9f67g8h0i12
Revises: i8e56f7g9h01
Create Date: 2025-12-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'j9f67g8h0i12'
down_revision: Union[str, Sequence[str], None] = 'i8e56f7g9h01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add calendar_event_id column to interactions table."""
    op.add_column(
        'interactions',
        sa.Column(
            'calendar_event_id',
            sa.String(length=255),
            nullable=True,
            comment='Google Calendar event ID for linking to calendar',
        )
    )


def downgrade() -> None:
    """Remove calendar_event_id column from interactions table."""
    op.drop_column('interactions', 'calendar_event_id')
