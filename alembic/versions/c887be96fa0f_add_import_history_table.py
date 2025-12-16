"""add import_history table

Revision ID: c887be96fa0f
Revises: f6116538178f
Create Date: 2025-12-08 18:33:18.067065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c887be96fa0f'
down_revision: Union[str, Sequence[str], None] = 'f6116538178f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types if they don't exist
    importsource = postgresql.ENUM('linkedin', 'google_contacts', 'csv', 'other', name='importsource', create_type=False)
    importstatus = postgresql.ENUM('success', 'partial', 'failed', name='importstatus', create_type=False)

    # Create enums conditionally
    importsource.create(op.get_bind(), checkfirst=True)
    importstatus.create(op.get_bind(), checkfirst=True)

    # Create import_history table
    op.create_table('import_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', importsource, nullable=False),
        sa.Column('status', importstatus, nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('records_parsed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('organizations_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('import_history')
    op.execute("DROP TYPE IF EXISTS importstatus")
    op.execute("DROP TYPE IF EXISTS importsource")
