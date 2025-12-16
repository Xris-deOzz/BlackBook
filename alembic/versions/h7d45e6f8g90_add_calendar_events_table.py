"""add_calendar_events_table

Revision ID: h7d45e6f8g90
Revises: g6c34d5e7f89
Create Date: 2025-12-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'h7d45e6f8g90'
down_revision: Union[str, Sequence[str], None] = 'g6c34d5e7f89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create calendar_events table for caching Google Calendar events."""
    op.create_table('calendar_events',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('google_account_id', sa.UUID(), nullable=False),
        sa.Column('google_event_id', sa.String(length=255), nullable=False, comment='Google Calendar event ID'),
        sa.Column('summary', sa.String(length=500), nullable=True, comment='Event title/summary'),
        sa.Column('description', sa.Text(), nullable=True, comment='Event description'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False, comment='Event start time'),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False, comment='Event end time'),
        sa.Column('location', sa.String(length=500), nullable=True, comment='Event location or video call link'),
        sa.Column('attendees', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of attendees [{email, name, response_status}]'),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Whether this is part of a recurring event'),
        sa.Column('recurring_event_id', sa.String(length=255), nullable=True, comment='ID of the recurring event series'),
        sa.Column('organizer_email', sa.String(length=255), nullable=True, comment='Email of the event organizer'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['google_account_id'], ['google_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('google_account_id', 'google_event_id', name='uq_calendar_events_account_event')
    )
    op.create_index('idx_calendar_events_start', 'calendar_events', ['start_time'], unique=False)
    op.create_index('idx_calendar_events_account', 'calendar_events', ['google_account_id'], unique=False)
    op.create_index('idx_calendar_events_end', 'calendar_events', ['end_time'], unique=False)


def downgrade() -> None:
    """Drop calendar_events table."""
    op.drop_index('idx_calendar_events_end', table_name='calendar_events')
    op.drop_index('idx_calendar_events_account', table_name='calendar_events')
    op.drop_index('idx_calendar_events_start', table_name='calendar_events')
    op.drop_table('calendar_events')
