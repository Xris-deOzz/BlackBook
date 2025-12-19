"""Add settings table

Revision ID: db9c13132abd
Revises: x3t01u2v4w56
Create Date: 2025-12-14 13:33:15.616024

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'db9c13132abd'
down_revision: Union[str, Sequence[str], None] = 'x3t01u2v4w56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create settings table
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settings_id'), 'settings', ['id'], unique=False)
    op.create_index(op.f('ix_settings_key'), 'settings', ['key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_settings_key'), table_name='settings')
    op.drop_index(op.f('ix_settings_id'), table_name='settings')
    op.drop_table('settings')
