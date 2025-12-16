"""add duplicate exclusions table

Revision ID: y4u12v3w5x67
Revises: x3t01u2v4w56
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'y4u12v3w5x67'
down_revision = 'db9c13132abd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create duplicate_exclusions table
    op.create_table(
        'duplicate_exclusions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('person1_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('person2_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['person1_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person2_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique index on the pair
    op.create_index(
        'ix_duplicate_exclusions_pair',
        'duplicate_exclusions',
        ['person1_id', 'person2_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_duplicate_exclusions_pair', table_name='duplicate_exclusions')
    op.drop_table('duplicate_exclusions')
