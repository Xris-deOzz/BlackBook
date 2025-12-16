"""add_birthday_to_persons

Revision ID: k0g78h9i1j23
Revises: j9f67g8h0i12
Create Date: 2025-12-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'k0g78h9i1j23'
down_revision: Union[str, Sequence[str], None] = 'j9f67g8h0i12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add birthday column to persons table."""
    op.add_column(
        'persons',
        sa.Column(
            'birthday',
            sa.Date(),
            nullable=True,
            comment='Person birthday (day and month, year optional)',
        )
    )


def downgrade() -> None:
    """Remove birthday column from persons table."""
    op.drop_column('persons', 'birthday')
