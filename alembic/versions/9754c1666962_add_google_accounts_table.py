"""add_google_accounts_table

Revision ID: 9754c1666962
Revises: b91b9dd8073a
Create Date: 2025-12-08 07:53:10.700971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9754c1666962'
down_revision: Union[str, Sequence[str], None] = 'b91b9dd8073a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create google_accounts table for OAuth credential storage."""
    op.create_table('google_accounts',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('credentials_encrypted', sa.Text(), nullable=False, comment='AES-256 encrypted OAuth refresh token'),
        sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=True, comment='OAuth scopes granted (e.g., gmail.readonly, calendar.readonly)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_google_accounts_email')
    )


def downgrade() -> None:
    """Drop google_accounts table."""
    op.drop_table('google_accounts')
