"""Create organization type lookup tables

Revision ID: t9p67q8r0s12
Revises: s8o56p7q9r01
Create Date: 2025-12-11

Create the two-tier organization type system:
- organization_categories: High-level categories (Investment Firm, Company, etc.)
- organization_types: Specific types within categories (VC, PE, Startup, etc.)
- investment_profile_options: Multi-select options for investment profiles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 't9p67q8r0s12'
down_revision: Union[str, None] = 's8o56p7q9r01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create organization type lookup tables."""

    # Create organization_categories table
    op.create_table(
        'organization_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('has_investment_profile', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_organization_categories_code'),
    )
    op.create_index('ix_organization_categories_code', 'organization_categories', ['code'])

    # Create organization_types table
    op.create_table(
        'organization_types',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('profile_style', sa.String(50), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['category_id'], ['organization_categories.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('code', name='uq_organization_types_code'),
    )
    op.create_index('ix_organization_types_code', 'organization_types', ['code'])
    op.create_index('ix_organization_types_category_id', 'organization_types', ['category_id'])

    # Create investment_profile_options table
    op.create_table(
        'investment_profile_options',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('option_type', sa.String(50), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('option_type', 'code', name='uq_investment_option_type_code'),
    )
    op.create_index('ix_investment_profile_options_option_type', 'investment_profile_options', ['option_type'])


def downgrade() -> None:
    """Drop organization type lookup tables."""

    # Drop investment_profile_options table
    op.drop_index('ix_investment_profile_options_option_type', table_name='investment_profile_options')
    op.drop_table('investment_profile_options')

    # Drop organization_types table
    op.drop_index('ix_organization_types_category_id', table_name='organization_types')
    op.drop_index('ix_organization_types_code', table_name='organization_types')
    op.drop_table('organization_types')

    # Drop organization_categories table
    op.drop_index('ix_organization_categories_code', table_name='organization_categories')
    op.drop_table('organization_categories')
