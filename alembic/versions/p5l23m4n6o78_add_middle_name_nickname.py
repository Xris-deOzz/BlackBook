"""Add middle_name and nickname to persons

Revision ID: p5l23m4n6o78
Revises: o4k12l3m5n67
Create Date: 2025-12-09 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p5l23m4n6o78'
down_revision = 'o4k12l3m5n67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add middle_name column
    op.add_column('persons', sa.Column('middle_name', sa.String(150), nullable=True))

    # Add nickname column
    op.add_column('persons', sa.Column('nickname', sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column('persons', 'nickname')
    op.drop_column('persons', 'middle_name')
