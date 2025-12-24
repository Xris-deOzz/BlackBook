"""add person_google_links table and linkedin_id field

Revision ID: d9g45h6i7j89
Revises: ecfdba019152
Create Date: 2025-12-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd9g45h6i7j89'
down_revision = 'ecfdba019152'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create person_google_links table
    op.create_table(
        'person_google_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('google_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('google_resource_name', sa.String(255), nullable=False,
                  comment='Google People API resource name (e.g., people/c1234567890)'),
        sa.Column('google_etag', sa.String(100), nullable=True,
                  comment='Google etag for change detection'),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Last sync timestamp for this link'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['google_account_id'], ['google_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique constraint for google_account + resource_name
    op.create_unique_constraint(
        'uq_google_account_resource',
        'person_google_links',
        ['google_account_id', 'google_resource_name']
    )

    # Create indexes for fast lookups
    op.create_index(
        'ix_person_google_links_google_account',
        'person_google_links',
        ['google_account_id']
    )
    op.create_index(
        'ix_person_google_links_person',
        'person_google_links',
        ['person_id']
    )

    # Add linkedin_id field to persons table
    op.add_column(
        'persons',
        sa.Column('linkedin_id', sa.String(100), nullable=True,
                  comment="LinkedIn member ID extracted from URL (e.g., 'john-doe-123456')")
    )
    op.create_index(
        'ix_persons_linkedin_id',
        'persons',
        ['linkedin_id']
    )


def downgrade() -> None:
    # Drop linkedin_id from persons
    op.drop_index('ix_persons_linkedin_id', table_name='persons')
    op.drop_column('persons', 'linkedin_id')

    # Drop person_google_links table
    op.drop_index('ix_person_google_links_person', table_name='person_google_links')
    op.drop_index('ix_person_google_links_google_account', table_name='person_google_links')
    op.drop_constraint('uq_google_account_resource', 'person_google_links', type_='unique')
    op.drop_table('person_google_links')
