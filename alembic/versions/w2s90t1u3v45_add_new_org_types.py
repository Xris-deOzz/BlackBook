"""Add new organization types

Revision ID: w2s90t1u3v45
Revises: v1r89s0t2u34
Create Date: 2025-12-11

Add 4 new organization types:
- search_fund: Search Fund (pe_style) - already exists, skip
- fundless_sponsor: Fundless Sponsor (pe_style)
- independent_sponsor: Independent Sponsor (pe_style)
- venture_debt: Venture Debt (credit_style)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w2s90t1u3v45'
down_revision: Union[str, None] = 'v1r89s0t2u34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new organization types."""

    # Add new Investment Firm types (search_fund already exists from previous migration)
    op.execute("""
        INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'fundless_sponsor', 'Fundless Sponsor', 'pe_style', 16),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'independent_sponsor', 'Independent Sponsor', 'pe_style', 17),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'venture_debt', 'Venture Debt', 'credit_style', 18)
        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove the newly added organization types."""

    op.execute("""
        DELETE FROM organization_types
        WHERE code IN ('fundless_sponsor', 'independent_sponsor', 'venture_debt');
    """)
