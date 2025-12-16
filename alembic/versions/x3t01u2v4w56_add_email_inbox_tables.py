"""Add Email Inbox Integration tables

Revision ID: x3t01u2v4w56
Revises: w2s90t1u3v45
Create Date: 2025-12-13

Phase 6: Database schema for Gmail Inbox Integration
- email_messages: Cached Gmail message metadata
- email_person_links: Links between emails and CRM contacts
- email_sync_state: Sync progress tracking per account
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'x3t01u2v4w56'
down_revision: Union[str, None] = 'w2s90t1u3v45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Email Inbox Integration tables."""

    # 1. Create email_messages table
    op.create_table(
        'email_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('google_account_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('google_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gmail_message_id', sa.String(255), nullable=False,
                  comment='Gmail API message ID'),
        sa.Column('gmail_thread_id', sa.String(255), nullable=False,
                  comment='Gmail API thread ID (groups related messages)'),

        # Core metadata
        sa.Column('subject', sa.String(1000), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True,
                  comment='Short preview of email body from Gmail'),

        # Sender/Recipients
        sa.Column('from_email', sa.String(255), nullable=True),
        sa.Column('from_name', sa.String(255), nullable=True),
        sa.Column('to_emails', postgresql.JSONB(), server_default='[]',
                  comment='Array of {email, name} objects'),
        sa.Column('cc_emails', postgresql.JSONB(), server_default='[]'),
        sa.Column('bcc_emails', postgresql.JSONB(), server_default='[]'),

        # Status flags
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('is_starred', sa.Boolean(), server_default='false'),
        sa.Column('is_draft', sa.Boolean(), server_default='false'),
        sa.Column('is_sent', sa.Boolean(), server_default='false',
                  comment='True if from user sent folder'),
        sa.Column('labels', postgresql.JSONB(), server_default='[]',
                  comment='Gmail labels (INBOX, SENT, etc.)'),

        # Dates
        sa.Column('internal_date', sa.DateTime(timezone=True), nullable=True,
                  comment='Gmail internal timestamp (when message was received)'),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),

        # Attachment info
        sa.Column('has_attachments', sa.Boolean(), server_default='false'),
        sa.Column('attachment_count', sa.Integer(), server_default='0'),

        # Sync tracking
        sa.Column('history_id', sa.BigInteger(), nullable=True,
                  comment='Gmail history ID for incremental sync'),
        sa.Column('synced_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now()),

        # Constraints
        sa.UniqueConstraint('google_account_id', 'gmail_message_id',
                           name='uq_email_message_account_msg'),
    )

    # Indexes for email_messages
    op.create_index('idx_email_messages_account', 'email_messages', ['google_account_id'])
    op.create_index('idx_email_messages_thread', 'email_messages', ['gmail_thread_id'])
    op.create_index('idx_email_messages_date', 'email_messages',
                    [sa.text('internal_date DESC')])
    op.create_index('idx_email_messages_from', 'email_messages', ['from_email'])
    op.create_index('idx_email_messages_read', 'email_messages', ['is_read'])

    # 2. Create email_person_links table
    op.create_table(
        'email_person_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email_message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('email_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('link_type', sa.String(50), nullable=False,
                  comment='How person is connected: from, to, cc, mentioned'),
        sa.Column('linked_by', sa.String(50), server_default='auto',
                  comment='How link was created: auto or manual'),
        sa.Column('linked_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),

        # Constraints
        sa.UniqueConstraint('email_message_id', 'person_id', 'link_type',
                           name='uq_email_person_link_unique'),
    )

    # Indexes for email_person_links
    op.create_index('idx_email_person_links_email', 'email_person_links', ['email_message_id'])
    op.create_index('idx_email_person_links_person', 'email_person_links', ['person_id'])

    # 3. Create email_sync_state table
    op.create_table(
        'email_sync_state',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('google_account_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('google_accounts.id', ondelete='CASCADE'), nullable=False),

        # Gmail history tracking
        sa.Column('last_history_id', sa.BigInteger(), nullable=True,
                  comment='Gmail history ID for incremental sync'),

        # Sync timestamps
        sa.Column('last_full_sync_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the last full sync completed'),
        sa.Column('last_incremental_sync_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When the last incremental sync completed'),

        # Current status
        sa.Column('sync_status', sa.String(50), server_default='never_synced'),
        sa.Column('error_message', sa.Text(), nullable=True,
                  comment='Error details if last sync failed'),

        # Statistics
        sa.Column('messages_synced', sa.Integer(), server_default='0',
                  comment='Total messages synced from this account'),
        sa.Column('last_sync_message_count', sa.Integer(), server_default='0',
                  comment='Messages synced in last sync operation'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now()),

        # Constraints
        sa.UniqueConstraint('google_account_id', name='uq_email_sync_state_account'),
    )


def downgrade() -> None:
    """Drop Email Inbox Integration tables."""

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('email_sync_state')
    op.drop_table('email_person_links')
    op.drop_table('email_messages')
