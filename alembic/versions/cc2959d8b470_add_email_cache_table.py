"""add_email_cache_table

Revision ID: cc2959d8b470
Revises: dc879950ff96
Create Date: 2025-12-08 08:03:35.673683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc2959d8b470'
down_revision: Union[str, Sequence[str], None] = 'dc879950ff96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create email_cache table for temporary Gmail thread storage."""
    op.create_table('email_cache',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('google_account_id', sa.UUID(), nullable=False),
        sa.Column('gmail_thread_id', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('participants', postgresql.ARRAY(sa.Text()), nullable=True, comment='Email addresses involved in the thread'),
        sa.Column('last_message_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=True),
        sa.Column('cached_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['google_account_id'], ['google_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('person_id', 'gmail_thread_id', name='uq_email_cache_person_thread')
    )
    op.create_index('idx_email_cache_cached_at', 'email_cache', ['cached_at'], unique=False)
    op.create_index('idx_email_cache_person_id', 'email_cache', ['person_id'], unique=False)


def downgrade() -> None:
    """Drop email_cache table."""
    op.drop_index('idx_email_cache_person_id', table_name='email_cache')
    op.drop_index('idx_email_cache_cached_at', table_name='email_cache')
    op.drop_table('email_cache')
