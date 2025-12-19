"""Add bidirectional sync tables

Revision ID: a1a23b4c5d67
Revises: z5v23w4x6y78
Create Date: 2025-12-18

Tables added:
- sync_log: Audit trail for all sync operations
- archived_persons: Deleted contacts preserved for recovery
- sync_review_queue: Name/data conflicts pending manual review
- sync_settings: Schedule configuration (singleton)

Columns added to persons:
- sync_enabled, last_synced_at, sync_status, google_contact_ids

Columns added to google_accounts:
- sync_enabled, last_full_sync_at, next_sync_at
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = 'a1a23b4c5d67'
down_revision = 'z5v23w4x6y78'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # sync_log table - Audit trail
    # ========================================
    op.create_table(
        'sync_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='SET NULL'), nullable=True),
        sa.Column('google_account_id', UUID(as_uuid=True), sa.ForeignKey('google_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('direction', sa.String(25), nullable=False),  # 'google_to_blackbook', 'blackbook_to_google'
        sa.Column('action', sa.String(20), nullable=False),  # 'create', 'update', 'delete', 'archive', 'restore'
        sa.Column('status', sa.String(20), nullable=False),  # 'success', 'failed', 'pending_review'
        sa.Column('fields_changed', JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_sync_log_person', 'sync_log', ['person_id'])
    op.create_index('idx_sync_log_created', 'sync_log', ['created_at'])
    op.create_index('idx_sync_log_status', 'sync_log', ['status'])

    # ========================================
    # archived_persons table - Deleted contacts
    # ========================================
    op.create_table(
        'archived_persons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('original_person_id', UUID(as_uuid=True), nullable=False),
        sa.Column('person_data', JSONB, nullable=False),  # Full snapshot of person at deletion
        sa.Column('deleted_from', sa.String(20), nullable=False),  # 'google', 'blackbook'
        sa.Column('deleted_by_account_id', UUID(as_uuid=True), nullable=True),  # Which Google account triggered deletion
        sa.Column('google_contact_ids', JSONB, nullable=True),  # {"account_email": "people/c123...", ...}
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),  # 90 days from archived_at
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),  # NULL until restored
        sa.Column('restored_person_id', UUID(as_uuid=True), nullable=True),  # New person ID if restored
    )
    op.create_index('idx_archived_persons_original', 'archived_persons', ['original_person_id'])
    op.create_index('idx_archived_persons_archived', 'archived_persons', ['archived_at'])

    # ========================================
    # sync_review_queue table - Conflicts
    # ========================================
    op.create_table(
        'sync_review_queue',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('review_type', sa.String(30), nullable=False),  # 'name_conflict', 'data_conflict', 'duplicate_suspect'
        sa.Column('google_account_id', UUID(as_uuid=True), sa.ForeignKey('google_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('google_data', JSONB, nullable=False),  # Data from Google for comparison
        sa.Column('blackbook_data', JSONB, nullable=False),  # Data from BlackBook for comparison
        sa.Column('status', sa.String(20), server_default='pending'),  # 'pending', 'resolved', 'dismissed'
        sa.Column('resolution', JSONB, nullable=True),  # User's decision
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_sync_review_status', 'sync_review_queue', ['status'])

    # ========================================
    # sync_settings table - Configuration (singleton)
    # ========================================
    op.create_table(
        'sync_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('auto_sync_enabled', sa.Boolean, server_default='true'),
        sa.Column('sync_time_1', sa.Time, server_default=sa.text("'07:00'")),
        sa.Column('sync_time_2', sa.Time, server_default=sa.text("'21:00'")),
        sa.Column('sync_timezone', sa.String(50), server_default="'America/New_York'"),
        sa.Column('archive_retention_days', sa.Integer, server_default='90'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    # Insert default row (singleton)
    op.execute("INSERT INTO sync_settings (id) VALUES (gen_random_uuid())")

    # ========================================
    # Add columns to persons table
    # ========================================
    op.add_column('persons', sa.Column('sync_enabled', sa.Boolean, server_default='true'))
    op.add_column('persons', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('persons', sa.Column('sync_status', sa.String(20), server_default="'pending'"))
    op.add_column('persons', sa.Column('google_contact_ids', JSONB, server_default="'{}'"))

    # ========================================
    # Add columns to google_accounts table
    # ========================================
    op.add_column('google_accounts', sa.Column('sync_enabled', sa.Boolean, server_default='true'))
    op.add_column('google_accounts', sa.Column('last_full_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('google_accounts', sa.Column('next_sync_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from google_accounts
    op.drop_column('google_accounts', 'next_sync_at')
    op.drop_column('google_accounts', 'last_full_sync_at')
    op.drop_column('google_accounts', 'sync_enabled')
    
    # Remove columns from persons
    op.drop_column('persons', 'google_contact_ids')
    op.drop_column('persons', 'sync_status')
    op.drop_column('persons', 'last_synced_at')
    op.drop_column('persons', 'sync_enabled')
    
    # Drop tables (reverse order of creation)
    op.drop_table('sync_settings')
    op.drop_table('sync_review_queue')
    op.drop_table('archived_persons')
    op.drop_table('sync_log')
