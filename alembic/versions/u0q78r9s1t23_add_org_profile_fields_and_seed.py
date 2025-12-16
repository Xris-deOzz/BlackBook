"""Add organization profile fields and seed lookup data

Revision ID: u0q78r9s1t23
Revises: t9p67q8r0s12
Create Date: 2025-12-11

- Add category_id, type_id to organizations
- Add PE/Credit/Multi-Strategy/Public Markets investment profile fields
- Seed categories, types, and investment profile options
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'u0q78r9s1t23'
down_revision: Union[str, None] = 't9p67q8r0s12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new columns to organizations and seed lookup data."""

    # Add category_id and type_id columns to organizations
    op.add_column('organizations', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('type_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_organizations_category_id', 'organizations', 'organization_categories', ['category_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_organizations_type_id', 'organizations', 'organization_types', ['type_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_organizations_category_id', 'organizations', ['category_id'])
    op.create_index('ix_organizations_type_id', 'organizations', ['type_id'])

    # Add PE-Style Investment Profile fields
    op.add_column('organizations', sa.Column('deal_types', postgresql.ARRAY(sa.String(50)), nullable=True))
    op.add_column('organizations', sa.Column('target_revenue_min', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('target_revenue_max', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('target_ebitda_min', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('target_ebitda_max', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('control_preference', sa.String(20), nullable=True))
    op.add_column('organizations', sa.Column('industry_focus', postgresql.ARRAY(sa.String(100)), nullable=True))

    # Add Credit-Style Investment Profile fields
    op.add_column('organizations', sa.Column('credit_strategies', postgresql.ARRAY(sa.String(50)), nullable=True))

    # Add Multi-Strategy Investment Profile fields
    op.add_column('organizations', sa.Column('investment_styles', postgresql.ARRAY(sa.String(50)), nullable=True))
    op.add_column('organizations', sa.Column('asset_classes', postgresql.ARRAY(sa.String(50)), nullable=True))

    # Add Public Markets Investment Profile fields
    op.add_column('organizations', sa.Column('trading_strategies', postgresql.ARRAY(sa.String(50)), nullable=True))

    # Seed organization categories
    op.execute("""
        INSERT INTO organization_categories (code, name, description, has_investment_profile, sort_order) VALUES
        ('investment_firm', 'Investment Firm', 'VC, PE, Credit, and other investment firms', true, 1),
        ('company', 'Company', 'Operating businesses', false, 2),
        ('service_provider', 'Service Provider', 'Professional services firms', false, 3),
        ('other', 'Other', 'Non-profits, government, academic institutions', false, 4);
    """)

    # Seed organization types
    # Investment Firm types (15 types)
    op.execute("""
        INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'vc', 'Venture Capital', 'vc_style', 1),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'pe', 'Private Equity', 'pe_style', 2),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'growth_equity', 'Growth Equity', 'pe_style', 3),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'private_credit', 'Private Credit', 'credit_style', 4),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'family_office', 'Family Office', 'multi_strategy', 5),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'swf', 'Sovereign Wealth Fund', 'multi_strategy', 6),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'fof', 'Fund of Funds', 'multi_strategy', 7),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'hedge_fund', 'Hedge Fund', 'public_markets', 8),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'asset_manager', 'Asset Manager', 'public_markets', 9),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'ria', 'RIA/Wealth Manager', 'public_markets', 10),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'corporate_vc', 'Corporate VC', 'vc_style', 11),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'accelerator', 'Accelerator/Incubator', 'vc_style', 12),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'angel', 'Angel Investor', 'vc_style', 13),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'holdco', 'Holding Company', 'pe_style', 14),
        ((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'search_fund', 'Search Fund', 'pe_style', 15);
    """)

    # Company types (4 types)
    op.execute("""
        INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
        ((SELECT id FROM organization_categories WHERE code = 'company'), 'startup', 'Startup', NULL, 1),
        ((SELECT id FROM organization_categories WHERE code = 'company'), 'corp', 'Corporation', NULL, 2),
        ((SELECT id FROM organization_categories WHERE code = 'company'), 'bank', 'Bank', NULL, 3),
        ((SELECT id FROM organization_categories WHERE code = 'company'), 'insurance', 'Insurance Company', NULL, 4);
    """)

    # Service Provider types (5 types)
    op.execute("""
        INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
        ((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'law_firm', 'Law Firm', NULL, 1),
        ((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'ibank_consulting', 'Investment Bank / Consulting', NULL, 2),
        ((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'accounting', 'Accounting Firm', NULL, 3),
        ((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'headhunter', 'Headhunter / Recruiting', NULL, 4),
        ((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'placement_agent', 'Placement Agent', NULL, 5);
    """)

    # Other types (4 types)
    op.execute("""
        INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
        ((SELECT id FROM organization_categories WHERE code = 'other'), 'nonprofit', 'Non-Profit', NULL, 1),
        ((SELECT id FROM organization_categories WHERE code = 'other'), 'government', 'Government', NULL, 2),
        ((SELECT id FROM organization_categories WHERE code = 'other'), 'university', 'University/Academic', NULL, 3),
        ((SELECT id FROM organization_categories WHERE code = 'other'), 'other', 'Other', NULL, 4);
    """)

    # Seed investment profile options

    # VC Stage options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('vc_stage', 'pre_seed', 'Pre-Seed', 1),
        ('vc_stage', 'seed', 'Seed', 2),
        ('vc_stage', 'series_a', 'Series A', 3),
        ('vc_stage', 'series_b', 'Series B', 4),
        ('vc_stage', 'series_c', 'Series C', 5),
        ('vc_stage', 'series_d_plus', 'Series D+', 6),
        ('vc_stage', 'growth', 'Growth', 7);
    """)

    # VC Sector options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('vc_sector', 'saas', 'SaaS', 1),
        ('vc_sector', 'fintech', 'Fintech', 2),
        ('vc_sector', 'healthcare', 'Healthcare', 3),
        ('vc_sector', 'ai_ml', 'AI/ML', 4),
        ('vc_sector', 'consumer', 'Consumer', 5),
        ('vc_sector', 'enterprise', 'Enterprise', 6),
        ('vc_sector', 'marketplace', 'Marketplace', 7),
        ('vc_sector', 'deeptech', 'Deep Tech', 8),
        ('vc_sector', 'climate', 'Climate/Cleantech', 9),
        ('vc_sector', 'biotech', 'Biotech', 10),
        ('vc_sector', 'crypto_web3', 'Crypto/Web3', 11),
        ('vc_sector', 'ecommerce', 'E-Commerce', 12),
        ('vc_sector', 'edtech', 'EdTech', 13),
        ('vc_sector', 'proptech', 'PropTech', 14),
        ('vc_sector', 'insurtech', 'InsurTech', 15);
    """)

    # PE Deal Type options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('pe_deal_type', 'lbo', 'LBO', 1),
        ('pe_deal_type', 'growth_equity', 'Growth Equity', 2),
        ('pe_deal_type', 'recap', 'Recapitalization', 3),
        ('pe_deal_type', 'buyout', 'Buyout', 4),
        ('pe_deal_type', 'carveout', 'Carve-out', 5),
        ('pe_deal_type', 'rollup', 'Roll-up', 6),
        ('pe_deal_type', 'turnaround', 'Turnaround', 7),
        ('pe_deal_type', 'distressed', 'Distressed', 8);
    """)

    # PE Industry options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('pe_industry', 'business_services', 'Business Services', 1),
        ('pe_industry', 'healthcare_services', 'Healthcare Services', 2),
        ('pe_industry', 'industrials', 'Industrials', 3),
        ('pe_industry', 'consumer', 'Consumer', 4),
        ('pe_industry', 'financial_services', 'Financial Services', 5),
        ('pe_industry', 'technology', 'Technology', 6),
        ('pe_industry', 'media_telecom', 'Media & Telecom', 7),
        ('pe_industry', 'energy', 'Energy', 8),
        ('pe_industry', 'real_estate', 'Real Estate', 9),
        ('pe_industry', 'transportation', 'Transportation & Logistics', 10);
    """)

    # Control Preference options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('control_preference', 'majority', 'Majority Control', 1),
        ('control_preference', 'minority', 'Minority', 2),
        ('control_preference', 'either', 'Either', 3);
    """)

    # Credit Strategy options
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('credit_strategy', 'direct_lending', 'Direct Lending', 1),
        ('credit_strategy', 'mezzanine', 'Mezzanine', 2),
        ('credit_strategy', 'unitranche', 'Unitranche', 3),
        ('credit_strategy', 'abl', 'Asset-Based Lending', 4),
        ('credit_strategy', 'distressed_credit', 'Distressed Credit', 5),
        ('credit_strategy', 'special_situations', 'Special Situations', 6),
        ('credit_strategy', 'real_estate_debt', 'Real Estate Debt', 7),
        ('credit_strategy', 'infrastructure_debt', 'Infrastructure Debt', 8);
    """)

    # Investment Style options (for multi-strategy)
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('investment_style', 'direct', 'Direct Investing', 1),
        ('investment_style', 'co_invest', 'Co-Investment', 2),
        ('investment_style', 'fund_investor', 'Fund Investment', 3),
        ('investment_style', 'secondaries', 'Secondaries', 4);
    """)

    # Asset Class options (for multi-strategy)
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('asset_class', 'venture_capital', 'Venture Capital', 1),
        ('asset_class', 'private_equity', 'Private Equity', 2),
        ('asset_class', 'private_credit', 'Private Credit', 3),
        ('asset_class', 'real_estate', 'Real Estate', 4),
        ('asset_class', 'infrastructure', 'Infrastructure', 5),
        ('asset_class', 'hedge_funds', 'Hedge Funds', 6),
        ('asset_class', 'public_equities', 'Public Equities', 7),
        ('asset_class', 'fixed_income', 'Fixed Income', 8),
        ('asset_class', 'commodities', 'Commodities', 9);
    """)

    # Trading Strategy options (for public markets)
    op.execute("""
        INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
        ('trading_strategy', 'long_short', 'Long/Short Equity', 1),
        ('trading_strategy', 'activist', 'Activist', 2),
        ('trading_strategy', 'event_driven', 'Event-Driven', 3),
        ('trading_strategy', 'macro', 'Global Macro', 4),
        ('trading_strategy', 'quant', 'Quantitative', 5),
        ('trading_strategy', 'market_neutral', 'Market Neutral', 6),
        ('trading_strategy', 'long_only', 'Long Only', 7),
        ('trading_strategy', 'short_bias', 'Short Bias', 8),
        ('trading_strategy', 'multi_strategy', 'Multi-Strategy', 9);
    """)


def downgrade() -> None:
    """Remove new columns from organizations and delete seed data."""

    # Delete seed data (in reverse order of dependencies)
    op.execute("DELETE FROM investment_profile_options;")
    op.execute("DELETE FROM organization_types;")
    op.execute("DELETE FROM organization_categories;")

    # Drop new columns from organizations
    op.drop_column('organizations', 'trading_strategies')
    op.drop_column('organizations', 'asset_classes')
    op.drop_column('organizations', 'investment_styles')
    op.drop_column('organizations', 'credit_strategies')
    op.drop_column('organizations', 'industry_focus')
    op.drop_column('organizations', 'control_preference')
    op.drop_column('organizations', 'target_ebitda_max')
    op.drop_column('organizations', 'target_ebitda_min')
    op.drop_column('organizations', 'target_revenue_max')
    op.drop_column('organizations', 'target_revenue_min')
    op.drop_column('organizations', 'deal_types')

    # Drop foreign keys and indexes
    op.drop_index('ix_organizations_type_id', table_name='organizations')
    op.drop_index('ix_organizations_category_id', table_name='organizations')
    op.drop_constraint('fk_organizations_type_id', 'organizations', type_='foreignkey')
    op.drop_constraint('fk_organizations_category_id', 'organizations', type_='foreignkey')
    op.drop_column('organizations', 'type_id')
    op.drop_column('organizations', 'category_id')
