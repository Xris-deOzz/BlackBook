"""add_pending_contacts_table

Revision ID: i8e56f7g9h01
Revises: h7d45e6f8g90
Create Date: 2025-12-08 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'i8e56f7g9h01'
down_revision: Union[str, Sequence[str], None] = 'h7d45e6f8g90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pending_contacts table for unknown meeting attendees queue."""
    # Create the enum type first (check if exists)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'pendingcontactstatus'")
    )
    if not result.fetchone():
        op.execute("CREATE TYPE pendingcontactstatus AS ENUM ('pending', 'created', 'ignored')")

    # Use postgresql.ENUM with create_type=False to reference existing enum
    status_enum = postgresql.ENUM('pending', 'created', 'ignored', name='pendingcontactstatus', create_type=False)

    op.create_table('pending_contacts',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(length=255), nullable=False, comment='Email address of the unknown attendee'),
        sa.Column('name', sa.String(length=255), nullable=True, comment='Name from calendar event (if available)'),
        sa.Column('source_event_id', sa.UUID(), nullable=True, comment='Calendar event where this contact was first seen'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='When this contact was first discovered'),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default=sa.text('1'), comment='Number of events this contact appears in'),
        sa.Column('status', status_enum, nullable=False, server_default='pending', comment='Processing status: pending, created, ignored'),
        sa.Column('created_person_id', sa.UUID(), nullable=True, comment='Person record created from this pending contact'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['source_event_id'], ['calendar_events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_person_id'], ['persons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_pending_contacts_email')
    )
    op.create_index('idx_pending_contacts_status', 'pending_contacts', ['status'], unique=False)


def downgrade() -> None:
    """Drop pending_contacts table."""
    op.drop_index('idx_pending_contacts_status', table_name='pending_contacts')
    op.drop_table('pending_contacts')

    # Drop the enum type
    pendingcontactstatus = sa.Enum('pending', 'created', 'ignored', name='pendingcontactstatus')
    pendingcontactstatus.drop(op.get_bind(), checkfirst=True)
