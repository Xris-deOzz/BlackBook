"""Merge heads: bidirectional sync and tag subcategories

Revision ID: b7w56x7y9z01
Revises: a1a23b4c5d67, a6w45x6y8z90
Create Date: 2025-12-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7w56x7y9z01'
down_revision = ('a1a23b4c5d67', 'a6w45x6y8z90')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
