"""add_email_ignore_list_table

Revision ID: dc879950ff96
Revises: 9754c1666962
Create Date: 2025-12-08 07:56:31.958394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dc879950ff96'
down_revision: Union[str, Sequence[str], None] = '9754c1666962'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create email_ignore_list table for filtering unwanted emails."""
    # Create the ignore_pattern_type enum first
    ignore_pattern_type = postgresql.ENUM('email', 'domain', name='ignore_pattern_type', create_type=False)
    ignore_pattern_type.create(op.get_bind(), checkfirst=True)

    # Create the email_ignore_list table
    op.create_table('email_ignore_list',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('pattern', sa.String(length=255), nullable=False),
        sa.Column('pattern_type', ignore_pattern_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("pattern_type IN ('email', 'domain')", name='ck_email_ignore_list_pattern_type'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pattern', name='uq_email_ignore_list_pattern')
    )


def downgrade() -> None:
    """Drop email_ignore_list table."""
    op.drop_table('email_ignore_list')

    # Drop the enum type
    ignore_pattern_type = postgresql.ENUM('email', 'domain', name='ignore_pattern_type', create_type=False)
    ignore_pattern_type.drop(op.get_bind(), checkfirst=True)
