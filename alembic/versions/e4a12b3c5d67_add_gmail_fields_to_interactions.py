"""add_gmail_fields_to_interactions

Revision ID: e4a12b3c5d67
Revises: cc2959d8b470
Create Date: 2025-12-08 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4a12b3c5d67'
down_revision: Union[str, Sequence[str], None] = 'cc2959d8b470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Gmail tracking fields to interactions table."""
    # Create the interaction_source enum type
    interaction_source_enum = postgresql.ENUM(
        'manual', 'email', 'calendar',
        name='interaction_source',
        create_type=True
    )
    interaction_source_enum.create(op.get_bind(), checkfirst=True)

    # Add gmail_thread_id column
    op.add_column('interactions',
        sa.Column('gmail_thread_id', sa.String(length=255), nullable=True)
    )

    # Add gmail_message_id column
    op.add_column('interactions',
        sa.Column('gmail_message_id', sa.String(length=255), nullable=True)
    )

    # Add source column with default 'manual'
    op.add_column('interactions',
        sa.Column('source',
            postgresql.ENUM('manual', 'email', 'calendar', name='interaction_source', create_type=False),
            nullable=False,
            server_default='manual'
        )
    )

    # Create partial index for gmail_thread_id (only where not null)
    op.create_index(
        'idx_interactions_gmail_thread',
        'interactions',
        ['gmail_thread_id'],
        unique=False,
        postgresql_where=sa.text('gmail_thread_id IS NOT NULL')
    )


def downgrade() -> None:
    """Remove Gmail tracking fields from interactions table."""
    op.drop_index('idx_interactions_gmail_thread', table_name='interactions')
    op.drop_column('interactions', 'source')
    op.drop_column('interactions', 'gmail_message_id')
    op.drop_column('interactions', 'gmail_thread_id')

    # Drop the enum type
    interaction_source_enum = postgresql.ENUM(
        'manual', 'email', 'calendar',
        name='interaction_source'
    )
    interaction_source_enum.drop(op.get_bind(), checkfirst=True)
