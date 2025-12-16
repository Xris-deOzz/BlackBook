"""Add calendar_settings table

Revision ID: q6m34n5o7p89
Revises: 8b7083ac02f0
Create Date: 2025-12-10 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q6m34n5o7p89'
down_revision: Union[str, Sequence[str], None] = '8b7083ac02f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create calendar_settings table."""
    op.create_table('calendar_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='America/New_York', comment='IANA timezone identifier for calendar display'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop calendar_settings table."""
    op.drop_table('calendar_settings')
