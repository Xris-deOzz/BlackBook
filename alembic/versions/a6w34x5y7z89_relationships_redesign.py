"""Relationships section redesign - add my_relationship fields and new relationship types.

Revision ID: a6w34x5y7z89
Revises: z5v23w4x6y78
Create Date: 2025-12-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6w34x5y7z89"
down_revision: Union[str, None] = "z5v23w4x6y78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add category and display_order to relationship_types
    op.add_column(
        "relationship_types",
        sa.Column("category", sa.String(50), nullable=True, server_default="other"),
    )
    op.add_column(
        "relationship_types",
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="100"),
    )

    # Add my_relationship fields to persons
    op.add_column(
        "persons",
        sa.Column(
            "my_relationship_type_id",
            sa.UUID(),
            sa.ForeignKey("relationship_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "persons",
        sa.Column("my_relationship_notes", sa.Text(), nullable=True),
    )

    # Update existing relationship types with categories and display_order
    op.execute("""
        UPDATE relationship_types SET category = 'professional', display_order = 30
        WHERE name = 'Worked Together';

        UPDATE relationship_types SET category = 'professional', display_order = 34
        WHERE name = 'Reports To';

        UPDATE relationship_types SET category = 'professional', display_order = 35
        WHERE name = 'Manages';

        UPDATE relationship_types SET category = 'family', display_order = 10
        WHERE name = 'Family Member';

        UPDATE relationship_types SET category = 'introduction', display_order = 40
        WHERE name = 'Introduced By';

        UPDATE relationship_types SET category = 'introduction', display_order = 41
        WHERE name = 'Introduced To';

        UPDATE relationship_types SET category = 'education', display_order = 20
        WHERE name = 'College Classmate';

        UPDATE relationship_types SET category = 'other', display_order = 100
        WHERE name = 'Other';
    """)

    # Insert new relationship types
    op.execute("""
        INSERT INTO relationship_types (id, name, inverse_name, category, display_order, requires_organization, is_system, created_at)
        VALUES
        -- Family types (display_order 11-14)
        (gen_random_uuid(), 'Spouse', 'Spouse', 'family', 11, false, true, now()),
        (gen_random_uuid(), 'Child', 'Parent', 'family', 12, false, true, now()),
        (gen_random_uuid(), 'Parent', 'Child', 'family', 13, false, true, now()),
        (gen_random_uuid(), 'Sibling', 'Sibling', 'family', 14, false, true, now()),

        -- Personal types (display_order 50-59)
        (gen_random_uuid(), 'Friend', 'Friend', 'personal', 50, false, true, now()),
        (gen_random_uuid(), 'Acquaintance', 'Acquaintance', 'personal', 51, false, true, now()),
        (gen_random_uuid(), 'Met at Conference', 'Met at Conference', 'personal', 52, false, true, now()),
        (gen_random_uuid(), 'Met at Event', 'Met at Event', 'personal', 53, false, true, now()),
        (gen_random_uuid(), 'Former Coworker', 'Former Coworker', 'personal', 54, false, true, now()),
        (gen_random_uuid(), 'Referred By', 'Referred To', 'personal', 55, false, true, now()),
        (gen_random_uuid(), 'Referred To', 'Referred By', 'personal', 56, false, true, now()),

        -- Professional additions (display_order 31-33)
        (gen_random_uuid(), 'Business Partner', 'Business Partner', 'professional', 31, false, true, now()),
        (gen_random_uuid(), 'Mentor', 'Mentee', 'professional', 32, false, true, now()),
        (gen_random_uuid(), 'Mentee', 'Mentor', 'professional', 33, false, true, now())

        ON CONFLICT (name) DO NOTHING;
    """)


def downgrade() -> None:
    # Remove my_relationship fields from persons
    op.drop_column("persons", "my_relationship_notes")
    op.drop_column("persons", "my_relationship_type_id")

    # Remove new relationship types
    op.execute("""
        DELETE FROM relationship_types
        WHERE name IN (
            'Spouse', 'Child', 'Parent', 'Sibling',
            'Friend', 'Acquaintance', 'Met at Conference', 'Met at Event',
            'Former Coworker', 'Referred By', 'Referred To',
            'Business Partner', 'Mentor', 'Mentee'
        );
    """)

    # Remove category and display_order columns
    op.drop_column("relationship_types", "display_order")
    op.drop_column("relationship_types", "category")
