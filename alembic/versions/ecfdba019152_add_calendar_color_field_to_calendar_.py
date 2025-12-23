"""Add calendar_color field to calendar_events

Revision ID: ecfdba019152
Revises: c8x67y8z0a12
Create Date: 2025-12-22 22:20:43.914960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecfdba019152'
down_revision: Union[str, Sequence[str], None] = 'c8x67y8z0a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('calendar_events', sa.Column('calendar_color', sa.String(length=32), nullable=True, comment='Event color (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('calendar_events', 'calendar_color')
