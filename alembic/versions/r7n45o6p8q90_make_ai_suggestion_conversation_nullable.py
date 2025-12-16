"""Make ai_suggestions.conversation_id nullable

Revision ID: r7n45o6p8q90
Revises: q6m34n5o7p89
Create Date: 2025-12-10

Allow AI suggestions to be created without a conversation context,
enabling standalone tool usage (e.g., direct API calls or background jobs).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r7n45o6p8q90'
down_revision: Union[str, None] = 'q6m34n5o7p89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make conversation_id nullable in ai_suggestions table."""
    op.alter_column(
        'ai_suggestions',
        'conversation_id',
        existing_type=sa.UUID(),
        nullable=True
    )


def downgrade() -> None:
    """Revert conversation_id to NOT NULL (requires cleaning up NULL values first)."""
    # First delete any rows with NULL conversation_id
    op.execute("DELETE FROM ai_suggestions WHERE conversation_id IS NULL")

    op.alter_column(
        'ai_suggestions',
        'conversation_id',
        existing_type=sa.UUID(),
        nullable=False
    )
