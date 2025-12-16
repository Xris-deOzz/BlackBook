"""add_ai_quick_prompts

Revision ID: 8b7083ac02f0
Revises: p5l23m4n6o78
Create Date: 2025-12-10 09:39:28.101717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8b7083ac02f0'
down_revision: Union[str, Sequence[str], None] = 'p5l23m4n6o78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if enum already exists (in case of partial migration)
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'prompt_entity_type'"))
    enum_exists = result.fetchone() is not None

    if not enum_exists:
        # Create the prompt_entity_type enum only if it doesn't exist
        prompt_entity_type = sa.Enum('person', 'organization', 'both', name='prompt_entity_type')
        prompt_entity_type.create(op.get_bind(), checkfirst=True)

    # Create the ai_quick_prompts table using postgresql.ENUM with create_type=False
    prompt_entity_type_enum = postgresql.ENUM('person', 'organization', 'both', name='prompt_entity_type', create_type=False)

    op.create_table('ai_quick_prompts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False, comment='Short button text displayed to user'),
        sa.Column('prompt_text', sa.Text(), nullable=False, comment='Full prompt text sent to AI'),
        sa.Column('entity_type', prompt_entity_type_enum, nullable=False, comment='Which entity types this prompt applies to'),
        sa.Column('display_order', sa.Integer(), nullable=False, comment='Order in which prompts are displayed'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='Whether this prompt is currently enabled'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Seed default prompts
    op.execute("""
        INSERT INTO ai_quick_prompts (id, label, prompt_text, entity_type, display_order, is_active, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'Recent news', 'Find recent news and articles about this person or organization', 'both', 1, true, NOW(), NOW()),
            (gen_random_uuid(), 'Podcasts', 'Search for podcast appearances or interviews featuring this person or organization', 'both', 2, true, NOW(), NOW()),
            (gen_random_uuid(), 'Background', 'Provide a comprehensive background summary on this person or organization', 'both', 3, true, NOW(), NOW()),
            (gen_random_uuid(), 'Suggest updates', 'Suggest profile updates based on online research', 'both', 4, true, NOW(), NOW())
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_quick_prompts')

    # Drop the enum type
    prompt_entity_type = sa.Enum('person', 'organization', 'both', name='prompt_entity_type')
    prompt_entity_type.drop(op.get_bind(), checkfirst=True)
