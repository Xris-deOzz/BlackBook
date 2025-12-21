"""Add tag_subcategories table

Revision ID: a6w45x6y8z90
Revises: z5v23w4x6y78
Create Date: 2025-12-20

Updated: 2024-12-21 - Updated subcategory list to match actual Google Contact labels
Reference: docs/TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'a6w45x6y8z90'
down_revision = 'a6w34x5y7z89'
branch_labels = None
depends_on = None


# Default subcategories - matches app/models/tag_subcategory.py
DEFAULT_SUBCATEGORIES = [
    {"name": "Location", "default_color": "#3b82f6", "display_order": 1},          # Blue
    {"name": "Classmates", "default_color": "#06b6d4", "display_order": 2},        # Cyan
    {"name": "Education", "default_color": "#8b5cf6", "display_order": 3},         # Violet
    {"name": "Holidays", "default_color": "#f97316", "display_order": 4},          # Orange
    {"name": "Personal", "default_color": "#ec4899", "display_order": 5},          # Pink
    {"name": "Social", "default_color": "#22c55e", "display_order": 6},            # Green
    {"name": "Professional", "default_color": "#a855f7", "display_order": 7},      # Purple
    {"name": "Former Colleagues", "default_color": "#14b8a6", "display_order": 8}, # Teal
    {"name": "Investor Type", "default_color": "#6366f1", "display_order": 9},     # Indigo
    {"name": "Relationship Origin", "default_color": "#f43f5e", "display_order": 10}, # Rose
]


def upgrade() -> None:
    # Create tag_subcategories table
    op.create_table(
        'tag_subcategories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(100), unique=True, nullable=False),  # Increased from 50 to 100
        sa.Column('default_color', sa.String(20), nullable=False, default='#6b7280'),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow),
    )
    
    # Create index on name for faster lookups
    op.create_index('ix_tag_subcategories_name', 'tag_subcategories', ['name'])
    
    # Seed default subcategories
    tag_subcategories = sa.table(
        'tag_subcategories',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('default_color', sa.String),
        sa.column('display_order', sa.Integer),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    
    now = datetime.utcnow()
    for subcat in DEFAULT_SUBCATEGORIES:
        op.execute(
            tag_subcategories.insert().values(
                id=uuid.uuid4(),
                name=subcat["name"],
                default_color=subcat["default_color"],
                display_order=subcat["display_order"],
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index('ix_tag_subcategories_name', table_name='tag_subcategories')
    op.drop_table('tag_subcategories')
