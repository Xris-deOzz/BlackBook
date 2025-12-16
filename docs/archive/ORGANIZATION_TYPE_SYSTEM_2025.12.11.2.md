# Organization Type System Redesign Specification

**Version:** 2025.12.11.2
**Status:** Ready for Implementation
**Related Docs:** 
- `ORGANIZATION_PAGE_REDESIGN_2025.12.11.1.md` (✅ COMPLETED)
- `PERSON_PAGE_REDESIGN_2025.12.09.1.md`
- `CLAUDE_CODE_PROMPT_TYPE_SYSTEM_2025.12.11.md`

---

## CURRENT IMPLEMENTATION STATE

The Organization Page Redesign is **complete**. Current state:

### Existing OrgType Enum (6 values)
```python
class OrgType(str, PyEnum):
    investment_firm = "investment_firm"
    company = "company"
    law_firm = "law_firm"
    bank = "bank"
    accelerator = "accelerator"
    other = "other"
```

### Existing Investment Profile Fields (VC-style only)
- `investment_stages` (TEXT, comma-separated)
- `check_size_min` / `check_size_max` (INTEGER, in thousands)
- `investment_sectors` (TEXT, comma-separated)
- `geographic_focus` (TEXT)
- `fund_size` (INTEGER, in millions)
- `current_fund_name` (VARCHAR)
- `current_fund_year` (INTEGER)

### What This Spec Adds
1. Replace flat enum with two-tier lookup tables (Category → Type)
2. Add PE, Credit, Multi-Strategy, Public Markets profile fields
3. Dynamic form rendering based on profile_style
4. Admin UI for managing types and options

---

## 1. Executive Summary

### Problem Statement
The current organization type system uses a flat list of 20+ types with no hierarchy. This creates issues:
- Investment firms and regular companies mixed in one dropdown
- No way to conditionally show investment profile fields based on firm type
- Difficult to filter/search by broad category
- Adding new types requires code changes

### Solution
Implement a two-tier type system:
- **Tier 1: Category** - High-level classification (Investment Firm, Company, Service Provider, Other)
- **Tier 2: Type** - Specific type within category (VC, PE, Startup, Law Firm, etc.)

Add a lookup table that maps types to profile styles, enabling dynamic form rendering.

---

## 2. Organization Categories & Types

### 2.1 Category Definitions

| Category | Code | Description | Has Investment Profile? |
|----------|------|-------------|------------------------|
| Investment Firm | `investment_firm` | Makes investments as primary business | ✅ Yes (varies by type) |
| Company | `company` | Operating business, startup, enterprise | ❌ No |
| Service Provider | `service_provider` | Professional services firms | ❌ No |
| Other | `other` | Non-profits, government, academic, etc. | ❌ No |

### 2.2 Type Definitions by Category

#### Investment Firm Types

| Type Code | Display Label | Profile Style | Notes |
|-----------|---------------|---------------|-------|
| `vc` | Venture Capital | `vc_style` | Classic venture - Pre-Seed to Late Stage |
| `corporate_vc` | Corporate VC | `vc_style` | Strategic corporate venture arm |
| `accelerator` | Accelerator / Incubator / Studio | `vc_style` | Batch programs, pre-seed focus |
| `angel` | Angel(s) | `vc_style` | Individual or angel group |
| `pe` | Private Equity | `pe_style` | Buyouts, growth equity, control |
| `holdco` | Holding Company | `pe_style` | Permanent capital, operating cos |
| `pc` | Private Credit | `credit_style` | Direct lending, mezz, distressed |
| `family_office` | Family Office | `multi_strategy` | Flexible, multi-asset |
| `swf` | Sovereign Wealth Fund | `multi_strategy` | Government investment fund |
| `fof` | Fund of Funds | `multi_strategy` | Invests in funds |
| `hedge_activist` | Hedge Fund - Activist | `public_markets` | Activist positions |
| `hedge_alt` | Hedge Fund / Alternative AM | `public_markets` | Long/short, quant, macro |
| `shortseller` | Shortseller | `public_markets` | Short-only or short-biased |
| `am` | Asset Manager | `public_markets` | Traditional asset management |
| `ria` | RIA | `public_markets` | Registered Investment Advisor |
| `search_fund` | Search Fund | `pe_style` | Single-acquisition micro-PE vehicle |
| `fundless_sponsor` | Fundless Sponsor | `pe_style` | Deal-by-deal, no committed capital |
| `independent_sponsor` | Independent Sponsor | `pe_style` | Deal-by-deal PE without permanent fund |
| `venture_debt` | Venture Debt | `credit_style` | Debt financing for startups |

#### Company Types

| Type Code | Display Label | Profile Style | Notes |
|-----------|---------------|---------------|-------|
| `startup` | Startup | `null` | Early-stage company |
| `corp` | Corporation | `null` | Established business |
| `insurco` | Insurance Company | `null` | Insurance carrier |
| `bank` | Bank | `null` | Commercial/retail bank |

#### Service Provider Types

| Type Code | Display Label | Profile Style | Notes |
|-----------|---------------|---------------|-------|
| `law_firm` | Law Firm | `null` | Legal services |
| `ibank_consulting` | Investment Bank / Consulting | `null` | Advisory services |
| `headhunter` | Headhunting / Recruiting | `null` | Executive search |
| `accounting` | Accounting / Audit | `null` | Financial services |
| `pr_marketing` | PR / Marketing | `null` | Communications |

#### Other Types

| Type Code | Display Label | Profile Style | Notes |
|-----------|---------------|---------------|-------|
| `nonprofit` | Non-Profit / Think Tank | `null` | Research, policy, charity |
| `government` | Government Agency | `null` | Federal, state, local govt |
| `university` | University / Academic | `null` | Educational institution |
| `association` | Industry Association | `null` | Trade groups, professional orgs |

---

## 3. Investment Profile Styles

Each investment firm type maps to a profile style that determines which fields to display.

### 3.1 Profile Style: `vc_style`

**Applies to:** VC, Corporate VC, Accelerator, Angel

| Field | Type | Options/Format | Required |
|-------|------|----------------|----------|
| Investment Stages | Multi-select | Pre-Seed, Seed, Series A, Series B, Series C, Series D+, Growth, Late Stage | No |
| Min Check Size | Integer | In thousands (e.g., 500 = $500K) | No |
| Max Check Size | Integer | In thousands (e.g., 5000 = $5M) | No |
| Investment Sectors | Multi-select | See sector list below | No |
| Geographic Focus | Text | Free text, comma-separated | No |
| Total AUM | Integer | In millions (e.g., 500 = $500M) | No |
| Current Fund Name | Text | e.g., "Fund VI" | No |
| Current Fund Year | Integer | e.g., 2023 | No |

**VC Sectors:**
- SaaS
- Fintech
- Healthcare / Healthtech
- Consumer
- Enterprise
- AI/ML
- Biotech
- Cybersecurity
- Cleantech
- EdTech
- PropTech
- Marketplace
- Hardware
- DeepTech
- Crypto/Web3
- Other

### 3.2 Profile Style: `pe_style`

**Applies to:** PE, HoldCo, Search Fund, Fundless Sponsor, Independent Sponsor

| Field | Type | Options/Format | Required |
|-------|------|----------------|----------|
| Deal Types | Multi-select | LBO, Growth Equity, Recapitalization, Distressed, Add-on/Bolt-on, Carve-out, PIPE, Secondary | No |
| Min Deal Size | Integer | In millions (e.g., 50 = $50M) | No |
| Max Deal Size | Integer | In millions (e.g., 500 = $500M) | No |
| Target Revenue Min | Integer | In millions | No |
| Target Revenue Max | Integer | In millions | No |
| Target EBITDA Min | Integer | In millions | No |
| Target EBITDA Max | Integer | In millions | No |
| Control Preference | Single-select | Majority, Minority, Either | No |
| Industry Focus | Multi-select | See industry list below | No |
| Geographic Focus | Text | Free text | No |
| Total AUM | Integer | In millions | No |
| Current Fund Name | Text | | No |
| Current Fund Year | Integer | | No |

**PE Industries:**
- Business Services
- Healthcare Services
- Industrial / Manufacturing
- Consumer Products
- Financial Services
- Technology
- Media / Entertainment
- Transportation / Logistics
- Energy
- Real Estate
- Food & Beverage
- Retail
- Education
- Other

### 3.3 Profile Style: `credit_style`

**Applies to:** PC (Private Credit), Venture Debt

| Field | Type | Options/Format | Required |
|-------|------|----------------|----------|
| Credit Strategies | Multi-select | Direct Lending, Mezzanine, Distressed Debt, Asset-Based Lending, Unitranche, Specialty Finance, Venture Debt, Real Estate Debt | No |
| Min Deal Size | Integer | In millions | No |
| Max Deal Size | Integer | In millions | No |
| Target Company Revenue Min | Integer | In millions | No |
| Target Company Revenue Max | Integer | In millions | No |
| Target Company EBITDA Min | Integer | In millions | No |
| Target Company EBITDA Max | Integer | In millions | No |
| Industry Focus | Multi-select | Same as PE industries | No |
| Geographic Focus | Text | | No |
| Total AUM | Integer | In millions | No |
| Current Fund Name | Text | | No |
| Current Fund Year | Integer | | No |

### 3.4 Profile Style: `multi_strategy`

**Applies to:** Family Office, SWF, Fund of Funds

| Field | Type | Options/Format | Required |
|-------|------|----------------|----------|
| Investment Style | Multi-select | Direct Investment, Co-Investment, Fund Investment, Secondaries | No |
| Asset Classes | Multi-select | Venture Capital, Private Equity, Private Credit, Public Equity, Fixed Income, Real Estate, Infrastructure, Commodities, Hedge Funds | No |
| Min Investment Size | Integer | In millions | No |
| Max Investment Size | Integer | In millions | No |
| Geographic Focus | Text | | No |
| Total AUM | Integer | In millions | No |
| Sectors of Interest | Text | Free text | No |

### 3.5 Profile Style: `public_markets`

**Applies to:** Hedge Fund - Activist, Hedge Fund / Alt AM, Shortseller, AM, RIA

| Field | Type | Options/Format | Required |
|-------|------|----------------|----------|
| Strategies | Multi-select | Long/Short Equity, Long Only, Short Only, Activist, Event-Driven, Macro, Quant/Systematic, Credit, Multi-Strategy, Value, Growth | No |
| Asset Classes | Multi-select | Public Equity, Fixed Income, Commodities, Currencies, Derivatives | No |
| Geographic Focus | Text | | No |
| Total AUM | Integer | In millions | No |
| Sectors of Focus | Multi-select | Same as VC sectors | No |

---

## 4. Database Schema

### 4.1 New Tables

#### `organization_categories` (Lookup Table)
```sql
CREATE TABLE organization_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    has_investment_profile BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed data
INSERT INTO organization_categories (code, name, has_investment_profile, sort_order) VALUES
('investment_firm', 'Investment Firm', TRUE, 1),
('company', 'Company', FALSE, 2),
('service_provider', 'Service Provider', FALSE, 3),
('other', 'Other', FALSE, 4);
```

#### `organization_types` (Lookup Table)
```sql
CREATE TABLE organization_types (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES organization_categories(id) ON DELETE RESTRICT,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    profile_style VARCHAR(50),  -- 'vc_style', 'pe_style', 'credit_style', 'multi_strategy', 'public_markets', NULL
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX idx_organization_types_category ON organization_types(category_id);
CREATE INDEX idx_organization_types_code ON organization_types(code);
```

#### `investment_profile_options` (Lookup Table for Multi-selects)
```sql
CREATE TABLE investment_profile_options (
    id SERIAL PRIMARY KEY,
    option_type VARCHAR(50) NOT NULL,  -- 'vc_stage', 'vc_sector', 'pe_deal_type', 'pe_industry', etc.
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(option_type, code)
);

-- Index
CREATE INDEX idx_investment_profile_options_type ON investment_profile_options(option_type);
```

### 4.2 Modified Tables

#### `organizations` - Add Category Reference
```sql
-- Add new columns
ALTER TABLE organizations 
ADD COLUMN category_id INTEGER REFERENCES organization_categories(id),
ADD COLUMN type_id INTEGER REFERENCES organization_types(id);

-- Keep existing 'type' column temporarily for migration
-- Will be deprecated after data migration

-- Add index
CREATE INDEX idx_organizations_category ON organizations(category_id);
CREATE INDEX idx_organizations_type ON organizations(type_id);
```

#### `organizations` - Investment Profile Fields

The current implementation already has some VC-style fields. We need to add PE and Credit specific fields:

```sql
-- PE-Style fields (add to existing organizations table)
ALTER TABLE organizations
ADD COLUMN deal_types TEXT[],                    -- Array of deal type codes
ADD COLUMN target_revenue_min INTEGER,           -- In millions
ADD COLUMN target_revenue_max INTEGER,           -- In millions
ADD COLUMN target_ebitda_min INTEGER,            -- In millions
ADD COLUMN target_ebitda_max INTEGER,            -- In millions
ADD COLUMN control_preference VARCHAR(20),       -- 'majority', 'minority', 'either'
ADD COLUMN industry_focus TEXT[];                -- Array of industry codes

-- Credit-Style fields
ADD COLUMN credit_strategies TEXT[];             -- Array of credit strategy codes

-- Multi-Strategy fields
ADD COLUMN investment_styles TEXT[],             -- Array: 'direct', 'co_invest', 'fund_investor'
ADD COLUMN asset_classes TEXT[];                 -- Array of asset class codes

-- Public Markets fields
ADD COLUMN trading_strategies TEXT[];            -- Array of strategy codes

-- Rename existing fields for clarity (optional - check current names first)
-- investment_stages -> keep as is (used by VC)
-- investment_sectors -> keep as is (used by VC)
-- check_size_min/max -> keep as is (universal)
-- fund_size -> rename to total_aum for clarity
-- geographic_focus -> keep as is (universal)
```

### 4.3 Data Migration

```sql
-- Step 1: Populate organization_categories (done via seed)

-- Step 2: Populate organization_types with mapping to categories
-- (See seed data in section 4.4)

-- Step 3: Backfill category_id and type_id based on existing 'type' column
UPDATE organizations o
SET 
    category_id = oc.id,
    type_id = ot.id
FROM organization_types ot
JOIN organization_categories oc ON ot.category_id = oc.id
WHERE o.type = ot.name  -- Match on display name
   OR o.type = ot.code; -- Or match on code

-- Step 4: Handle unmapped types (set to 'other' category, create new type if needed)
UPDATE organizations 
SET category_id = (SELECT id FROM organization_categories WHERE code = 'other')
WHERE category_id IS NULL;

-- Step 5: After verification, make category_id NOT NULL
ALTER TABLE organizations ALTER COLUMN category_id SET NOT NULL;

-- Step 6: Eventually drop old 'type' column (separate migration after full testing)
-- ALTER TABLE organizations DROP COLUMN type;
```

### 4.4 Seed Data - Organization Types

```sql
-- Investment Firm Types
INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'vc', 'Venture Capital', 'vc_style', 1),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'corporate_vc', 'Corporate VC', 'vc_style', 2),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'accelerator', 'Accelerator / Incubator / Studio', 'vc_style', 3),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'angel', 'Angel(s)', 'vc_style', 4),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'pe', 'Private Equity', 'pe_style', 5),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'holdco', 'Holding Company', 'pe_style', 6),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'pc', 'Private Credit', 'credit_style', 7),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'family_office', 'Family Office', 'multi_strategy', 8),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'swf', 'Sovereign Wealth Fund', 'multi_strategy', 9),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'fof', 'Fund of Funds', 'multi_strategy', 10),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'hedge_activist', 'Hedge Fund - Activist', 'public_markets', 11),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'hedge_alt', 'Hedge Fund / Alternative AM', 'public_markets', 12),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'shortseller', 'Shortseller', 'public_markets', 13),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'am', 'Asset Manager', 'public_markets', 14),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'ria', 'RIA', 'public_markets', 15),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'search_fund', 'Search Fund', 'pe_style', 16),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'fundless_sponsor', 'Fundless Sponsor', 'pe_style', 17),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'independent_sponsor', 'Independent Sponsor', 'pe_style', 18),
((SELECT id FROM organization_categories WHERE code = 'investment_firm'), 'venture_debt', 'Venture Debt', 'credit_style', 19);

-- Company Types
INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
((SELECT id FROM organization_categories WHERE code = 'company'), 'startup', 'Startup', NULL, 1),
((SELECT id FROM organization_categories WHERE code = 'company'), 'corp', 'Corporation', NULL, 2),
((SELECT id FROM organization_categories WHERE code = 'company'), 'insurco', 'Insurance Company', NULL, 3),
((SELECT id FROM organization_categories WHERE code = 'company'), 'bank', 'Bank', NULL, 4);

-- Service Provider Types
INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'law_firm', 'Law Firm', NULL, 1),
((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'ibank_consulting', 'Investment Bank / Consulting', NULL, 2),
((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'headhunter', 'Headhunting / Recruiting', NULL, 3),
((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'accounting', 'Accounting / Audit', NULL, 4),
((SELECT id FROM organization_categories WHERE code = 'service_provider'), 'pr_marketing', 'PR / Marketing', NULL, 5);

-- Other Types
INSERT INTO organization_types (category_id, code, name, profile_style, sort_order) VALUES
((SELECT id FROM organization_categories WHERE code = 'other'), 'nonprofit', 'Non-Profit / Think Tank', NULL, 1),
((SELECT id FROM organization_categories WHERE code = 'other'), 'government', 'Government Agency', NULL, 2),
((SELECT id FROM organization_categories WHERE code = 'other'), 'university', 'University / Academic', NULL, 3),
((SELECT id FROM organization_categories WHERE code = 'other'), 'association', 'Industry Association', NULL, 4);
```

### 4.5 Seed Data - Investment Profile Options

```sql
-- VC Investment Stages
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('vc_stage', 'pre_seed', 'Pre-Seed', 1),
('vc_stage', 'seed', 'Seed', 2),
('vc_stage', 'series_a', 'Series A', 3),
('vc_stage', 'series_b', 'Series B', 4),
('vc_stage', 'series_c', 'Series C', 5),
('vc_stage', 'series_d_plus', 'Series D+', 6),
('vc_stage', 'growth', 'Growth', 7),
('vc_stage', 'late_stage', 'Late Stage', 8);

-- VC/Tech Sectors
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('vc_sector', 'saas', 'SaaS', 1),
('vc_sector', 'fintech', 'Fintech', 2),
('vc_sector', 'healthcare', 'Healthcare / Healthtech', 3),
('vc_sector', 'consumer', 'Consumer', 4),
('vc_sector', 'enterprise', 'Enterprise', 5),
('vc_sector', 'ai_ml', 'AI/ML', 6),
('vc_sector', 'biotech', 'Biotech', 7),
('vc_sector', 'cybersecurity', 'Cybersecurity', 8),
('vc_sector', 'cleantech', 'Cleantech', 9),
('vc_sector', 'edtech', 'EdTech', 10),
('vc_sector', 'proptech', 'PropTech', 11),
('vc_sector', 'marketplace', 'Marketplace', 12),
('vc_sector', 'hardware', 'Hardware', 13),
('vc_sector', 'deeptech', 'DeepTech', 14),
('vc_sector', 'crypto_web3', 'Crypto/Web3', 15),
('vc_sector', 'other', 'Other', 99);

-- PE Deal Types
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('pe_deal_type', 'lbo', 'LBO', 1),
('pe_deal_type', 'growth_equity', 'Growth Equity', 2),
('pe_deal_type', 'recap', 'Recapitalization', 3),
('pe_deal_type', 'distressed', 'Distressed', 4),
('pe_deal_type', 'add_on', 'Add-on / Bolt-on', 5),
('pe_deal_type', 'carve_out', 'Carve-out', 6),
('pe_deal_type', 'pipe', 'PIPE', 7),
('pe_deal_type', 'secondary', 'Secondary', 8);

-- PE/Credit Industries
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('pe_industry', 'business_services', 'Business Services', 1),
('pe_industry', 'healthcare_services', 'Healthcare Services', 2),
('pe_industry', 'industrial', 'Industrial / Manufacturing', 3),
('pe_industry', 'consumer_products', 'Consumer Products', 4),
('pe_industry', 'financial_services', 'Financial Services', 5),
('pe_industry', 'technology', 'Technology', 6),
('pe_industry', 'media_entertainment', 'Media / Entertainment', 7),
('pe_industry', 'transportation', 'Transportation / Logistics', 8),
('pe_industry', 'energy', 'Energy', 9),
('pe_industry', 'real_estate', 'Real Estate', 10),
('pe_industry', 'food_beverage', 'Food & Beverage', 11),
('pe_industry', 'retail', 'Retail', 12),
('pe_industry', 'education', 'Education', 13),
('pe_industry', 'other', 'Other', 99);

-- Credit Strategies
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('credit_strategy', 'direct_lending', 'Direct Lending', 1),
('credit_strategy', 'mezzanine', 'Mezzanine', 2),
('credit_strategy', 'distressed_debt', 'Distressed Debt', 3),
('credit_strategy', 'abl', 'Asset-Based Lending', 4),
('credit_strategy', 'unitranche', 'Unitranche', 5),
('credit_strategy', 'specialty_finance', 'Specialty Finance', 6),
('credit_strategy', 'venture_debt', 'Venture Debt', 7),
('credit_strategy', 'real_estate_debt', 'Real Estate Debt', 8);

-- Multi-Strategy Investment Styles
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('investment_style', 'direct', 'Direct Investment', 1),
('investment_style', 'co_invest', 'Co-Investment', 2),
('investment_style', 'fund_investor', 'Fund Investment', 3),
('investment_style', 'secondaries', 'Secondaries', 4);

-- Asset Classes
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('asset_class', 'venture_capital', 'Venture Capital', 1),
('asset_class', 'private_equity', 'Private Equity', 2),
('asset_class', 'private_credit', 'Private Credit', 3),
('asset_class', 'public_equity', 'Public Equity', 4),
('asset_class', 'fixed_income', 'Fixed Income', 5),
('asset_class', 'real_estate', 'Real Estate', 6),
('asset_class', 'infrastructure', 'Infrastructure', 7),
('asset_class', 'commodities', 'Commodities', 8),
('asset_class', 'hedge_funds', 'Hedge Funds', 9);

-- Public Markets Trading Strategies
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('trading_strategy', 'long_short', 'Long/Short Equity', 1),
('trading_strategy', 'long_only', 'Long Only', 2),
('trading_strategy', 'short_only', 'Short Only', 3),
('trading_strategy', 'activist', 'Activist', 4),
('trading_strategy', 'event_driven', 'Event-Driven', 5),
('trading_strategy', 'macro', 'Macro', 6),
('trading_strategy', 'quant', 'Quant / Systematic', 7),
('trading_strategy', 'credit', 'Credit', 8),
('trading_strategy', 'multi_strategy', 'Multi-Strategy', 9),
('trading_strategy', 'value', 'Value', 10),
('trading_strategy', 'growth', 'Growth', 11);

-- Control Preferences (for PE)
INSERT INTO investment_profile_options (option_type, code, name, sort_order) VALUES
('control_preference', 'majority', 'Majority', 1),
('control_preference', 'minority', 'Minority', 2),
('control_preference', 'either', 'Either', 3);
```

---

## 5. API Endpoints

### 5.1 Lookup Endpoints (Read-Only for UI)

```
GET /api/v1/lookups/organization-categories
    Response: [{ id, code, name, has_investment_profile, sort_order }]

GET /api/v1/lookups/organization-types
    Query params: ?category_id=1 (optional filter)
    Response: [{ id, code, name, category_id, category_code, profile_style, sort_order }]

GET /api/v1/lookups/organization-types/{code}
    Response: { id, code, name, category, profile_style }

GET /api/v1/lookups/investment-profile-options
    Query params: ?option_type=vc_stage (required)
    Response: [{ id, code, name, sort_order }]

GET /api/v1/lookups/investment-profile-options/all
    Response: { vc_stage: [...], vc_sector: [...], pe_deal_type: [...], ... }
```

### 5.2 Admin Endpoints (CRUD for Types)

```
POST /api/v1/admin/organization-categories
    Body: { code, name, description, has_investment_profile, sort_order }

PUT /api/v1/admin/organization-categories/{id}
    Body: { name, description, has_investment_profile, sort_order, is_active }

POST /api/v1/admin/organization-types
    Body: { category_id, code, name, profile_style, description, sort_order }

PUT /api/v1/admin/organization-types/{id}
    Body: { name, profile_style, description, sort_order, is_active }

DELETE /api/v1/admin/organization-types/{id}
    - Soft delete (set is_active = false)
    - Prevent if organizations exist with this type

POST /api/v1/admin/investment-profile-options
    Body: { option_type, code, name, sort_order }

PUT /api/v1/admin/investment-profile-options/{id}
    Body: { name, sort_order, is_active }
```

### 5.3 Updated Organization Endpoints

```
GET /api/v1/organizations
    - Include category_name and type_name in response
    - Add filter: ?category=investment_firm

GET /api/v1/organizations/{id}
    - Include full category and type objects
    - Include profile_style for frontend rendering

POST /api/v1/organizations
    Body: { name, category_id, type_id, ... }
    - category_id required
    - type_id required
    - Validate type belongs to category

PUT /api/v1/organizations/{id}
    - If category_id changes, validate type_id matches new category
    - Clear investment profile fields if category changes from investment_firm
```

---

## 6. Frontend Changes

### 6.1 Organization Create/Edit Form

**Cascading Dropdown Behavior:**

```javascript
// When category changes:
1. Filter type dropdown to show only types in selected category
2. Clear current type selection
3. Show/hide investment profile section based on category.has_investment_profile
4. If investment_firm, show/hide specific fields based on type.profile_style
```

**Form Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Basic Information                                           │
├─────────────────────────────────────────────────────────────┤
│ Name:        [_______________________________________]      │
│                                                             │
│ Category:    [Investment Firm ▼]                            │
│                                                             │
│ Type:        [Venture Capital ▼]  ← Filtered by category    │
│                                                             │
│ Website:     [_______________________________________]      │
│ Description: [_______________________________________]      │
│              [_______________________________________]      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ▼ Investment Profile               (Only for Investment Firm)│
├─────────────────────────────────────────────────────────────┤
│ << Dynamic fields based on type.profile_style >>            │
│                                                             │
│ For VC: stages, check size, sectors, fund info              │
│ For PE: deal types, revenue/EBITDA targets, control, etc.   │
│ For Credit: strategies, deal size, targets                  │
│ etc.                                                        │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Organization Detail Page

**Investment Profile Section - Dynamic Rendering:**

```html
{% if organization.category.has_investment_profile %}
<section class="investment-profile">
    <h3>Investment Profile</h3>
    
    {% if organization.type.profile_style == 'vc_style' %}
        {% include 'organizations/sections/_investment_profile_vc.html' %}
    {% elif organization.type.profile_style == 'pe_style' %}
        {% include 'organizations/sections/_investment_profile_pe.html' %}
    {% elif organization.type.profile_style == 'credit_style' %}
        {% include 'organizations/sections/_investment_profile_credit.html' %}
    {% elif organization.type.profile_style == 'multi_strategy' %}
        {% include 'organizations/sections/_investment_profile_multi.html' %}
    {% elif organization.type.profile_style == 'public_markets' %}
        {% include 'organizations/sections/_investment_profile_public.html' %}
    {% endif %}
</section>
{% endif %}
```

### 6.3 Person Employment Form

**Quick Add Organization Modal:**

```
┌─────────────────────────────────────────────────────────────┐
│ Add New Organization                                    [X] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Name:     [Union Square Ventures_____________________]      │
│                                                             │
│ Category: [Investment Firm ▼]                               │
│           ┌─────────────────┐                               │
│           │ Investment Firm │                               │
│           │ Company         │                               │
│           │ Service Provider│                               │
│           │ Other           │                               │
│           └─────────────────┘                               │
│                                                             │
│ Type:     [VC ▼]                                            │
│           ┌──────────────────────────────┐                  │
│           │ Venture Capital              │                  │
│           │ Corporate VC                 │                  │
│           │ Accelerator / Incubator      │                  │
│           │ Angel(s)                     │                  │
│           │ Private Equity               │                  │
│           │ ...                          │                  │
│           └──────────────────────────────┘                  │
│                                                             │
│ Website:  [https://usv.com_______________________] (opt)    │
│                                                             │
│                              [Cancel]  [Create & Select]    │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Organization Search/Filter

**Filter Panel Updates:**

```
┌─────────────────────────────────┐
│ Filters                         │
├─────────────────────────────────┤
│ Category:                       │
│ [x] Investment Firm             │
│ [ ] Company                     │
│ [ ] Service Provider            │
│ [ ] Other                       │
│                                 │
│ Type: (filtered by category)    │
│ [x] VC                          │
│ [x] PE                          │
│ [ ] Private Credit              │
│ [ ] Family Office               │
│ ...                             │
│                                 │
│ Profile Style:                  │
│ [ ] VC-Style                    │
│ [ ] PE-Style                    │
│ ...                             │
└─────────────────────────────────┘
```

---

## 7. Admin UI for Managing Types

### 7.1 Settings Page - Organization Types

**Location:** Settings → Organization Types

```
┌─────────────────────────────────────────────────────────────┐
│ Organization Type Management                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Categories                              [+ Add Category]    │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Investment Firm    │ Has Profile │ 15 types │ [Edit]   ││
│ │ Company            │ No Profile  │ 4 types  │ [Edit]   ││
│ │ Service Provider   │ No Profile  │ 5 types  │ [Edit]   ││
│ │ Other              │ No Profile  │ 4 types  │ [Edit]   ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ Types in: [Investment Firm ▼]            [+ Add Type]       │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ VC              │ vc_style      │ 45 orgs │ [Edit] [x] ││
│ │ Corporate VC    │ vc_style      │ 12 orgs │ [Edit] [x] ││
│ │ PE              │ pe_style      │ 23 orgs │ [Edit] [x] ││
│ │ Private Credit  │ credit_style  │ 8 orgs  │ [Edit] [x] ││
│ │ ...                                                     ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ Investment Profile Options               [+ Add Option]     │
│ Option Type: [VC Stages ▼]                                  │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Pre-Seed  │ pre_seed  │ [↑] [↓] [Edit] [x]             ││
│ │ Seed      │ seed      │ [↑] [↓] [Edit] [x]             ││
│ │ Series A  │ series_a  │ [↑] [↓] [Edit] [x]             ││
│ │ ...                                                     ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Phases

### Phase A: Database Schema (4-6 hours)
1. Create migration for new lookup tables
2. Create migration to add columns to organizations
3. Create SQLAlchemy models for lookup tables
4. Write seed data scripts
5. Create data migration to backfill existing organizations
6. Test migrations up/down

### Phase B: API Endpoints (4-6 hours)
1. Create Pydantic schemas for lookup tables
2. Create lookup router with GET endpoints
3. Create admin router with CRUD endpoints
4. Update organization schemas to include category/type
5. Update organization router to use new structure
6. Add validation for category-type relationship

### Phase C: Frontend - Organization Forms (6-8 hours)
1. Update organization create form with cascading dropdowns
2. Update organization edit form
3. Create dynamic investment profile section templates (5 profile styles)
4. Implement HTMX for cascading dropdown behavior
5. Update person employment quick-add organization modal
6. Test all form flows

### Phase D: Frontend - Organization Detail Page (4-6 hours)
1. Update detail page to use dynamic profile templates
2. Create profile section templates for each style
3. Update sidebar to show category/type
4. Test display for all profile styles

### Phase E: Frontend - Admin UI (4-6 hours)
1. Create settings page for organization type management
2. Add/edit/delete categories
3. Add/edit/delete types
4. Add/edit/reorder investment profile options
5. Validation and error handling

### Phase F: Search & Filters (2-4 hours)
1. Update organization list page filters
2. Add category filter
3. Update type filter to be category-aware
4. Test filter combinations

### Phase G: Testing & Data Migration (4-6 hours)
1. Test all CRUD operations
2. Verify data migration accuracy
3. Test edge cases (type changes, category changes)
4. Performance testing with large datasets
5. Fix any issues

**Total Estimated Effort:** 28-42 hours

---

## 9. Files to Create/Modify

### New Files

**Models:**
- `app/models/organization_category.py`
- `app/models/organization_type.py`
- `app/models/investment_profile_option.py`

**Schemas:**
- `app/schemas/organization_category.py`
- `app/schemas/organization_type.py`
- `app/schemas/investment_profile_option.py`
- `app/schemas/lookups.py` (combined response schemas)

**Routers:**
- `app/routers/lookups.py`
- `app/routers/admin/organization_types.py`

**Templates:**
- `app/templates/organizations/sections/_investment_profile_vc.html`
- `app/templates/organizations/sections/_investment_profile_pe.html`
- `app/templates/organizations/sections/_investment_profile_credit.html`
- `app/templates/organizations/sections/_investment_profile_multi.html`
- `app/templates/organizations/sections/_investment_profile_public.html`
- `app/templates/settings/organization_types.html`

**Migrations:**
- `alembic/versions/xxx_create_organization_lookup_tables.py`
- `alembic/versions/xxx_add_category_to_organizations.py`
- `alembic/versions/xxx_add_pe_credit_profile_fields.py`
- `alembic/versions/xxx_seed_organization_types.py`
- `alembic/versions/xxx_backfill_organization_categories.py`

### Modified Files

**Models:**
- `app/models/organization.py` - Add category_id, type_id, new profile fields

**Schemas:**
- `app/schemas/organization.py` - Update create/update/response schemas

**Routers:**
- `app/routers/organizations.py` - Update CRUD operations

**Templates:**
- `app/templates/organizations/detail.html` - Dynamic profile section
- `app/templates/organizations/edit.html` - Cascading dropdowns
- `app/templates/organizations/new.html` - Cascading dropdowns
- `app/templates/organizations/_form.html` - Form updates
- `app/templates/organizations/list.html` - Filter updates
- `app/templates/persons/sections/_employment.html` - Quick-add modal update

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data migration errors | Medium | High | Run migration on backup first, validate counts |
| Existing integrations break | Low | Medium | Keep old 'type' column temporarily |
| UI complexity increases | Medium | Medium | Good UX with cascading dropdowns, sensible defaults |
| Performance with lookups | Low | Low | Cache lookup data, index properly |
| Type changes mid-record | Medium | Medium | Clear profile fields when type changes |

---

## 11. Open Questions

1. **Default category for new orgs?** Should there be a default or force selection?
   - Recommendation: Force selection (no default)

2. **What happens to old 'type' column?** Keep for backward compatibility or drop?
   - Recommendation: Keep for 3 months, then migrate and drop

3. **Should users be able to add custom types?** Or admin-only?
   - Recommendation: Admin-only via settings page

4. **Validation strictness?** Allow mismatched category/type during transition?
   - Recommendation: Strict validation after migration complete

---

## 12. Success Criteria

- [ ] All existing organizations have category_id and type_id populated
- [ ] Organization create/edit forms work with cascading dropdowns
- [ ] Investment profile sections render correctly for all 5 profile styles
- [ ] Person employment form can quick-add organizations with proper type
- [ ] Admin can add/edit/delete types and options
- [ ] Filters work correctly with new category/type structure
- [ ] No data loss during migration
- [ ] Performance acceptable (<500ms page loads)

---

## Appendix A: Type Mapping from Airtable

| Airtable Type | New Category | New Type Code | Profile Style |
|---------------|--------------|---------------|---------------|
| Accelerator / Incubator / Studio | investment_firm | accelerator | vc_style |
| AM | investment_firm | am | public_markets |
| Angel(s) | investment_firm | angel | vc_style |
| Corp | company | corp | null |
| Corporate VC | investment_firm | corporate_vc | vc_style |
| Family Office | investment_firm | family_office | multi_strategy |
| Fund of Funds | investment_firm | fof | multi_strategy |
| Headhunting Firm | service_provider | headhunter | null |
| Hedge Fund - Activist | investment_firm | hedge_activist | public_markets |
| Hedge Fund / Alternative AM | investment_firm | hedge_alt | public_markets |
| HoldCo | investment_firm | holdco | pe_style |
| iBank \| Consulting | service_provider | ibank_consulting | null |
| InsurCo | company | insurco | null |
| Non-Profit Think Tank | other | nonprofit | null |
| PC | investment_firm | pc | credit_style |
| PE | investment_firm | pe | pe_style |
| RIA | investment_firm | ria | public_markets |
| Shortseller | investment_firm | shortseller | public_markets |
| SWF | investment_firm | swf | multi_strategy |
| VC | investment_firm | vc | vc_style |
