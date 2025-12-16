"""Add AI Research Assistant tables

Revision ID: m2i90j1k3l45
Revises: l1h89i0j2k34
Create Date: 2025-12-09

Phase 5A: Database schema for AI features
- ai_providers: Available AI provider configurations
- ai_api_keys: Encrypted API key storage
- ai_conversations: Chat conversation metadata
- ai_messages: Individual messages within conversations
- ai_data_access_settings: Privacy/access controls
- ai_suggestions: AI-generated field suggestions
- record_snapshots: Point-in-time entity backups
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'm2i90j1k3l45'
down_revision: Union[str, None] = 'c887be96fa0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create AI Research Assistant tables."""

    # Create enum types
    ai_provider_type = postgresql.ENUM(
        'openai', 'anthropic', 'google', 'ollama',
        name='ai_provider_type',
        create_type=False
    )
    ai_message_role = postgresql.ENUM(
        'user', 'assistant', 'system', 'tool',
        name='ai_message_role',
        create_type=False
    )
    ai_suggestion_status = postgresql.ENUM(
        'pending', 'accepted', 'rejected',
        name='ai_suggestion_status',
        create_type=False
    )
    change_source_type = postgresql.ENUM(
        'manual', 'ai_suggestion', 'ai_auto', 'import',
        name='change_source_type',
        create_type=False
    )

    # Create enums conditionally
    ai_provider_type.create(op.get_bind(), checkfirst=True)
    ai_message_role.create(op.get_bind(), checkfirst=True)
    ai_suggestion_status.create(op.get_bind(), checkfirst=True)
    change_source_type.create(op.get_bind(), checkfirst=True)

    # 1. Create ai_providers table
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, comment='Display name for the provider'),
        sa.Column('api_type', ai_provider_type, nullable=False, comment='Provider type (openai, anthropic, google, ollama)'),
        sa.Column('base_url', sa.String(length=255), nullable=True, comment='Custom API endpoint URL (optional)'),
        sa.Column('is_local', sa.Boolean(), nullable=False, server_default='false', comment='True for local providers like Ollama'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Whether provider is enabled for use'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Create ai_api_keys table
    op.create_table(
        'ai_api_keys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider_id', sa.UUID(), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False, comment='AES-256 encrypted API key'),
        sa.Column('label', sa.String(length=100), nullable=True, comment='User-defined label for this key'),
        sa.Column('is_valid', sa.Boolean(), nullable=True, comment='Result of last validation test (null = not tested)'),
        sa.Column('last_tested', sa.DateTime(timezone=True), nullable=True, comment='Timestamp of last validation test'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_api_keys_provider_id', 'ai_api_keys', ['provider_id'])

    # 3. Create ai_conversations table
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=True, comment='Optional link to Person being researched'),
        sa.Column('organization_id', sa.UUID(), nullable=True, comment='Optional link to Organization being researched'),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='New Conversation', comment='Conversation title'),
        sa.Column('provider_name', sa.String(length=50), nullable=True, comment='AI provider used (e.g., openai, anthropic)'),
        sa.Column('model_name', sa.String(length=100), nullable=True, comment='Specific model used (e.g., gpt-4o, claude-3-sonnet)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_conversations_person_id', 'ai_conversations', ['person_id'])
    op.create_index('ix_ai_conversations_organization_id', 'ai_conversations', ['organization_id'])

    # 4. Create ai_messages table
    op.create_table(
        'ai_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('role', ai_message_role, nullable=False, comment='Message role (user, assistant, system, tool)'),
        sa.Column('content', sa.Text(), nullable=False, comment='Message text content'),
        sa.Column('tokens_in', sa.Integer(), nullable=True, comment='Input tokens used (for API calls)'),
        sa.Column('tokens_out', sa.Integer(), nullable=True, comment='Output tokens generated (for API calls)'),
        sa.Column('tool_calls_json', postgresql.JSONB(), nullable=True, comment='Tool calls made by assistant (JSON array)'),
        sa.Column('sources_json', postgresql.JSONB(), nullable=True, comment='Source citations (JSON array)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_messages_conversation_id', 'ai_messages', ['conversation_id'])

    # 5. Create ai_data_access_settings table (singleton)
    op.create_table(
        'ai_data_access_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('allow_notes', sa.Boolean(), nullable=False, server_default='true', comment='Include notes field in AI context'),
        sa.Column('allow_tags', sa.Boolean(), nullable=False, server_default='true', comment='Include tags in AI context'),
        sa.Column('allow_interactions', sa.Boolean(), nullable=False, server_default='true', comment='Include interaction history summaries'),
        sa.Column('allow_linkedin', sa.Boolean(), nullable=False, server_default='true', comment='Include LinkedIn URLs in AI context'),
        sa.Column('auto_apply_suggestions', sa.Boolean(), nullable=False, server_default='false', comment='Auto-apply AI suggestions without approval'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. Create ai_suggestions table
    op.create_table(
        'ai_suggestions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False, comment="Entity type: 'person' or 'organization'"),
        sa.Column('entity_id', sa.UUID(), nullable=False, comment='UUID of the entity to update'),
        sa.Column('field_name', sa.String(length=100), nullable=False, comment="Field name to update (e.g., 'title', 'website')"),
        sa.Column('current_value', sa.Text(), nullable=True, comment='Current field value (for comparison)'),
        sa.Column('suggested_value', sa.Text(), nullable=False, comment='AI-suggested new value'),
        sa.Column('confidence', sa.Float(), nullable=True, comment='AI confidence score (0.0 to 1.0)'),
        sa.Column('source_url', sa.String(length=500), nullable=True, comment='URL where AI found this information'),
        sa.Column('status', ai_suggestion_status, nullable=False, server_default='pending', comment='Suggestion status: pending, accepted, rejected'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True, comment='When the suggestion was accepted or rejected'),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_suggestions_conversation_id', 'ai_suggestions', ['conversation_id'])
    op.create_index('ix_ai_suggestions_entity', 'ai_suggestions', ['entity_type', 'entity_id'])
    op.create_index('ix_ai_suggestions_status', 'ai_suggestions', ['status'])

    # 7. Create record_snapshots table
    op.create_table(
        'record_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False, comment="Entity type: 'person' or 'organization'"),
        sa.Column('entity_id', sa.UUID(), nullable=False, comment='UUID of the entity'),
        sa.Column('snapshot_json', postgresql.JSONB(), nullable=False, comment='Complete entity state as JSON'),
        sa.Column('change_source', change_source_type, nullable=False, comment='What triggered this snapshot'),
        sa.Column('change_description', sa.String(length=255), nullable=True, comment='Human-readable description of the change'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_record_snapshots_entity', 'record_snapshots', ['entity_type', 'entity_id'])

    # Seed default AI providers
    op.execute("""
        INSERT INTO ai_providers (id, name, api_type, is_local, is_active, created_at)
        VALUES
            (gen_random_uuid(), 'OpenAI', 'openai', false, true, now()),
            (gen_random_uuid(), 'Claude', 'anthropic', false, true, now()),
            (gen_random_uuid(), 'Gemini', 'google', false, true, now()),
            (gen_random_uuid(), 'Ollama', 'ollama', true, false, now())
    """)

    # Create default data access settings (singleton)
    op.execute("""
        INSERT INTO ai_data_access_settings (id, allow_notes, allow_tags, allow_interactions, allow_linkedin, auto_apply_suggestions, created_at, updated_at)
        VALUES (gen_random_uuid(), true, true, true, true, false, now(), now())
    """)


def downgrade() -> None:
    """Drop AI Research Assistant tables."""

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('record_snapshots')
    op.drop_table('ai_suggestions')
    op.drop_table('ai_data_access_settings')
    op.drop_table('ai_messages')
    op.drop_table('ai_conversations')
    op.drop_table('ai_api_keys')
    op.drop_table('ai_providers')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS change_source_type")
    op.execute("DROP TYPE IF EXISTS ai_suggestion_status")
    op.execute("DROP TYPE IF EXISTS ai_message_role")
    op.execute("DROP TYPE IF EXISTS ai_provider_type")
