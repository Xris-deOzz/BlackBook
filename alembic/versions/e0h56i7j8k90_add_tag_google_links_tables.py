"""add tag_google_links and tag_sync_log tables

Revision ID: e0h56i7j8k90
Revises: d9g45h6i7j89
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e0h56i7j8k90'
down_revision = 'd9g45h6i7j89'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tag_google_links table
    op.create_table(
        'tag_google_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('google_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('google_group_resource_name', sa.String(100), nullable=True,
                  comment='Google contactGroup resource name (e.g., contactGroups/abc123def456)'),
        sa.Column('google_group_name', sa.String(255), nullable=False,
                  comment='Label name in Google for display'),
        sa.Column('sync_direction', sa.String(20), nullable=False, server_default='bidirectional',
                  comment='Sync direction: bidirectional, to_google, from_google'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(20), nullable=True,
                  comment='Status: success, error, pending'),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['google_account_id'], ['google_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique constraint: prevent duplicate links (same tag to same account)
    op.create_unique_constraint(
        'uq_tag_google_link',
        'tag_google_links',
        ['tag_id', 'google_account_id']
    )

    # Create indexes for fast lookups
    op.create_index(
        'idx_tag_google_links_tag',
        'tag_google_links',
        ['tag_id']
    )
    op.create_index(
        'idx_tag_google_links_account',
        'tag_google_links',
        ['google_account_id']
    )
    op.create_index(
        'idx_tag_google_links_resource',
        'tag_google_links',
        ['google_group_resource_name']
    )

    # Create tag_sync_log table
    op.create_table(
        'tag_sync_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_google_link_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('google_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(30), nullable=False,
                  comment='Action: link_created, link_deleted, member_added_to_google, etc.'),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('person_name', sa.String(255), nullable=True,
                  comment='Snapshot of person name for audit even if person deleted'),
        sa.Column('direction', sa.String(20), nullable=True,
                  comment='Direction: to_google, from_google, initial'),
        sa.Column('details', postgresql.JSONB(), nullable=True,
                  comment='Additional context as JSON'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success',
                  comment='Status: success, error'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['tag_google_link_id'], ['tag_google_links.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['google_account_id'], ['google_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for sync log queries
    op.create_index(
        'idx_tag_sync_log_link',
        'tag_sync_log',
        ['tag_google_link_id']
    )
    op.create_index(
        'idx_tag_sync_log_created',
        'tag_sync_log',
        ['created_at'],
        postgresql_using='btree',
        postgresql_ops={'created_at': 'DESC'}
    )
    op.create_index(
        'idx_tag_sync_log_tag',
        'tag_sync_log',
        ['tag_id']
    )


def downgrade() -> None:
    # Drop tag_sync_log table
    op.drop_index('idx_tag_sync_log_tag', table_name='tag_sync_log')
    op.drop_index('idx_tag_sync_log_created', table_name='tag_sync_log')
    op.drop_index('idx_tag_sync_log_link', table_name='tag_sync_log')
    op.drop_table('tag_sync_log')

    # Drop tag_google_links table
    op.drop_index('idx_tag_google_links_resource', table_name='tag_google_links')
    op.drop_index('idx_tag_google_links_account', table_name='tag_google_links')
    op.drop_index('idx_tag_google_links_tag', table_name='tag_google_links')
    op.drop_constraint('uq_tag_google_link', 'tag_google_links', type_='unique')
    op.drop_table('tag_google_links')
