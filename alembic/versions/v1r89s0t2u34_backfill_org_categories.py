"""Backfill existing organizations with category/type

Revision ID: v1r89s0t2u34
Revises: u0q78r9s1t23
Create Date: 2025-12-11

Map existing org_type enum values to new category_id/type_id:
- investment_firm -> investment_firm category, vc type
- company -> company category, corp type
- law_firm -> service_provider category, law_firm type
- bank -> company category, bank type
- accelerator -> investment_firm category, accelerator type
- other -> other category, other type
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v1r89s0t2u34'
down_revision: Union[str, None] = 'u0q78r9s1t23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill category_id and type_id based on existing org_type."""

    # investment_firm -> investment_firm category, vc type (default)
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'investment_firm'),
            type_id = (SELECT id FROM organization_types WHERE code = 'vc')
        WHERE org_type = 'investment_firm';
    """)

    # company -> company category, corp type
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'company'),
            type_id = (SELECT id FROM organization_types WHERE code = 'corp')
        WHERE org_type = 'company';
    """)

    # law_firm -> service_provider category, law_firm type
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'service_provider'),
            type_id = (SELECT id FROM organization_types WHERE code = 'law_firm')
        WHERE org_type = 'law_firm';
    """)

    # bank -> company category, bank type
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'company'),
            type_id = (SELECT id FROM organization_types WHERE code = 'bank')
        WHERE org_type = 'bank';
    """)

    # accelerator -> investment_firm category, accelerator type
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'investment_firm'),
            type_id = (SELECT id FROM organization_types WHERE code = 'accelerator')
        WHERE org_type = 'accelerator';
    """)

    # other -> other category, other type
    op.execute("""
        UPDATE organizations
        SET category_id = (SELECT id FROM organization_categories WHERE code = 'other'),
            type_id = (SELECT id FROM organization_types WHERE code = 'other')
        WHERE org_type = 'other';
    """)


def downgrade() -> None:
    """Clear backfilled category_id and type_id values."""

    op.execute("""
        UPDATE organizations
        SET category_id = NULL, type_id = NULL;
    """)
