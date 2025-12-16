"""Add Search API providers

Revision ID: n3j01k2l4m56
Revises: m2i90j1k3l45
Create Date: 2025-12-09

Phase 5C: Search API providers for AI research
- Extends ai_provider_type enum with brave_search, youtube, listen_notes
- Seeds search provider entries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n3j01k2l4m56'
down_revision: Union[str, None] = 'm2i90j1k3l45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add search API provider types and seed providers."""

    # Add new enum values to ai_provider_type
    # PostgreSQL requires ALTER TYPE to add new values
    # We need to use COMMIT to finalize enum changes before using them
    # This is done by executing outside of transaction
    connection = op.get_bind()

    # Add enum values outside transaction
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE ai_provider_type ADD VALUE IF NOT EXISTS 'brave_search'"))
    connection.execute(sa.text("ALTER TYPE ai_provider_type ADD VALUE IF NOT EXISTS 'youtube'"))
    connection.execute(sa.text("ALTER TYPE ai_provider_type ADD VALUE IF NOT EXISTS 'listen_notes'"))
    connection.execute(sa.text("BEGIN"))

    # Seed search API providers
    op.execute("""
        INSERT INTO ai_providers (id, name, api_type, is_local, is_active, created_at)
        VALUES
            (gen_random_uuid(), 'Brave Search', 'brave_search', false, true, now()),
            (gen_random_uuid(), 'YouTube', 'youtube', false, true, now()),
            (gen_random_uuid(), 'Listen Notes', 'listen_notes', false, true, now())
    """)


def downgrade() -> None:
    """Remove search API providers (enum values cannot be removed in PostgreSQL)."""

    # Delete search providers
    op.execute("""
        DELETE FROM ai_providers
        WHERE api_type IN ('brave_search', 'youtube', 'listen_notes')
    """)

    # Note: PostgreSQL does not support removing enum values
    # The enum values will remain but unused after downgrade
