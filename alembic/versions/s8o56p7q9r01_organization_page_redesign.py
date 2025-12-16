"""Organization page redesign - Phase A

Revision ID: s8o56p7q9r01
Revises: r7n45o6p8q90
Create Date: 2025-12-11

Add new tables and columns for organization page redesign:
- organization_offices: Track multiple office locations per organization
- organization_relationship_status: Track personal relationship with organizations
- Add social links (linkedin, twitter, pitchbook, angellist) to organizations
- Add investment profile fields for VC/PE firms
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 's8o56p7q9r01'
down_revision: Union[str, None] = 'r7n45o6p8q90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create new tables and add columns for organization page redesign."""

    # Create organization_offices table
    op.create_table(
        'organization_offices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('office_type', sa.String(50), nullable=False, server_default='regional'),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('address', sa.String(255), nullable=True),
        sa.Column('is_headquarters', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_organization_offices_organization_id', 'organization_offices', ['organization_id'])

    # Create organization_relationship_status table
    op.create_table(
        'organization_relationship_status',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('primary_contact_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('relationship_warmth', sa.String(20), nullable=True, server_default='unknown'),
        sa.Column('intro_available_via_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('next_followup_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['primary_contact_id'], ['persons.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['intro_available_via_id'], ['persons.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('organization_id', name='uq_org_relationship_status_org'),
    )
    op.create_index('ix_organization_relationship_status_organization_id', 'organization_relationship_status', ['organization_id'])

    # Add social link columns to organizations
    op.add_column('organizations', sa.Column('linkedin_url', sa.String(500), nullable=True))
    op.add_column('organizations', sa.Column('twitter_url', sa.String(500), nullable=True))
    op.add_column('organizations', sa.Column('pitchbook_url', sa.String(500), nullable=True))
    op.add_column('organizations', sa.Column('angellist_url', sa.String(500), nullable=True))

    # Add investment profile columns to organizations (for VC/PE firms)
    op.add_column('organizations', sa.Column('investment_stages', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('check_size_min', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('check_size_max', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('investment_sectors', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('geographic_focus', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('fund_size', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('current_fund_name', sa.String(200), nullable=True))
    op.add_column('organizations', sa.Column('current_fund_year', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove tables and columns added for organization page redesign."""

    # Drop investment profile columns from organizations
    op.drop_column('organizations', 'current_fund_year')
    op.drop_column('organizations', 'current_fund_name')
    op.drop_column('organizations', 'fund_size')
    op.drop_column('organizations', 'geographic_focus')
    op.drop_column('organizations', 'investment_sectors')
    op.drop_column('organizations', 'check_size_max')
    op.drop_column('organizations', 'check_size_min')
    op.drop_column('organizations', 'investment_stages')

    # Drop social link columns from organizations
    op.drop_column('organizations', 'angellist_url')
    op.drop_column('organizations', 'pitchbook_url')
    op.drop_column('organizations', 'twitter_url')
    op.drop_column('organizations', 'linkedin_url')

    # Drop organization_relationship_status table
    op.drop_index('ix_organization_relationship_status_organization_id', table_name='organization_relationship_status')
    op.drop_table('organization_relationship_status')

    # Drop organization_offices table
    op.drop_index('ix_organization_offices_organization_id', table_name='organization_offices')
    op.drop_table('organization_offices')
