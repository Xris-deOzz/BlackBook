# Claude Code Prompt - Organization Type System Implementation

**Date:** 2025.12.11
**Project:** `C:\Users\ossow\OneDrive\PerunsBlackBook`

## Quick Context

Self-hosted personal CRM. The Organization Page Redesign is **complete**. Now implementing a two-tier type system with lookup tables and profile-style-specific forms.

## Read These First

1. `Claude_Code_Context.md` - Full project context
2. `docs/ORGANIZATION_TYPE_SYSTEM_2025.12.11.2.md` - **Full specification for this task**
3. `docs/ORGANIZATION_PAGE_REDESIGN_2025.12.11.1.md` - Reference for current implementation

## Current State

The Org Page Redesign is complete with:
- VC-style investment profile fields (stages, sectors, check size, fund info)
- `OrgType` enum with 6 values: `investment_firm`, `company`, `law_firm`, `bank`, `accelerator`, `other`
- Office locations, relationship status, affiliated people, interaction history all working

## What Needs to Be Built

### 1. Two-Tier Type System

**Replace flat OrgType enum with:**

```
Tier 1: organization_categories (lookup table)
├── Investment Firm (has_investment_profile=true)
├── Company (has_investment_profile=false)
├── Service Provider (has_investment_profile=false)
└── Other (has_investment_profile=false)

Tier 2: organization_types (lookup table)
├── Investment Firm types: VC, PE, PC, Family Office, Search Fund, etc. (19 types)
├── Company types: Startup, Corp, InsurCo, Bank (4 types)
├── Service Provider types: Law Firm, iBank/Consulting, etc. (5 types)
└── Other types: Non-Profit, Government, University, etc. (4 types)
```

Each type has a `profile_style`: `vc_style`, `pe_style`, `credit_style`, `multi_strategy`, `public_markets`, or `null`

### 2. Profile-Style-Specific Fields

**VC-Style** (already exists): stages, check size, sectors, fund info

**PE-Style** (NEW fields needed) - applies to PE, HoldCo, Search Fund, Fundless Sponsor, Independent Sponsor:
- deal_types: TEXT[] (LBO, Growth Equity, Recap, etc.)
- target_revenue_min/max: INTEGER (in millions)
- target_ebitda_min/max: INTEGER (in millions)
- control_preference: VARCHAR (majority, minority, either)
- industry_focus: TEXT[]

**Credit-Style** (NEW fields needed) - applies to PC (Private Credit), Venture Debt:
- credit_strategies: TEXT[] (Direct Lending, Mezzanine, etc.)
- Uses PE fields for revenue/EBITDA targets

**Multi-Strategy** (NEW fields needed):
- investment_styles: TEXT[] (Direct, Co-Invest, Fund Investor)
- asset_classes: TEXT[]

**Public Markets** (NEW fields needed):
- trading_strategies: TEXT[]
- Uses asset_classes from multi-strategy

### 3. Investment Profile Options Lookup Table

Store all multi-select options in `investment_profile_options` table:
- vc_stage (Pre-Seed, Seed, Series A, etc.)
- vc_sector (SaaS, Fintech, AI/ML, etc.)
- pe_deal_type (LBO, Growth Equity, etc.)
- pe_industry (Business Services, Healthcare, etc.)
- credit_strategy (Direct Lending, Mezzanine, etc.)
- etc.

### 4. Cascading Dropdowns in Forms

When creating/editing an organization:
1. Select Category (filters available types)
2. Select Type (shows profile-style-specific fields)
3. Investment Profile section shows/hides based on category.has_investment_profile
4. Profile fields change based on type.profile_style

### 5. Admin UI

Settings page at `/settings/organization-types` to:
- View/edit categories
- Add/edit/deactivate types
- Manage investment profile options (reorder, add, deactivate)

## Implementation Phases

### Phase A: Database Schema (4-6 hours)
1. Create migration for `organization_categories` table
2. Create migration for `organization_types` table  
3. Create migration for `investment_profile_options` table
4. Add new columns to `organizations` for PE/Credit/Multi/Public fields
5. Add `category_id` and `type_id` foreign keys to `organizations`
6. Create seed data for all categories, types, and options
7. Create data migration to backfill existing orgs based on current `org_type` enum
8. Create SQLAlchemy models

### Phase B: API Endpoints (4-6 hours)
1. Create lookup router: GET categories, types, options
2. Create admin router: CRUD for categories, types, options
3. Update organization create/update to use category_id/type_id
4. Add validation: type must belong to selected category

### Phase C: Frontend Forms (6-8 hours)
1. Update organization create form with cascading category → type dropdowns
2. Update organization edit form similarly
3. Create dynamic investment profile templates for each profile_style:
   - `_investment_profile_vc.html` (already exists, refactor)
   - `_investment_profile_pe.html` (new)
   - `_investment_profile_credit.html` (new)
   - `_investment_profile_multi.html` (new)
   - `_investment_profile_public.html` (new)
4. Update person employment quick-add modal to use cascading dropdowns
5. HTMX for dynamic form updates when type changes

### Phase D: Admin UI (4-6 hours)
1. Create `/settings/organization-types` page
2. Category management section
3. Type management section (filtered by category)
4. Options management section (grouped by option_type)
5. Drag-and-drop reordering for options

### Phase E: Search & Filters (2-4 hours)
1. Update organization list page with category filter
2. Update type filter to be category-aware
3. Test filter combinations

### Phase F: Testing & Migration (4-6 hours)
1. Test all CRUD operations
2. Verify data migration accuracy
3. Test cascading dropdown behavior
4. Test profile-style switching

## Key Database Tables

```sql
-- Categories
CREATE TABLE organization_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    has_investment_profile BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Types
CREATE TABLE organization_types (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES organization_categories(id),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    profile_style VARCHAR(50),  -- 'vc_style', 'pe_style', etc.
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Multi-select options
CREATE TABLE investment_profile_options (
    id SERIAL PRIMARY KEY,
    option_type VARCHAR(50) NOT NULL,  -- 'vc_stage', 'pe_deal_type', etc.
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(option_type, code)
);

-- New columns on organizations table
ALTER TABLE organizations ADD COLUMN category_id INTEGER REFERENCES organization_categories(id);
ALTER TABLE organizations ADD COLUMN type_id INTEGER REFERENCES organization_types(id);
-- PE fields
ALTER TABLE organizations ADD COLUMN deal_types TEXT[];
ALTER TABLE organizations ADD COLUMN target_revenue_min INTEGER;
ALTER TABLE organizations ADD COLUMN target_revenue_max INTEGER;
ALTER TABLE organizations ADD COLUMN target_ebitda_min INTEGER;
ALTER TABLE organizations ADD COLUMN target_ebitda_max INTEGER;
ALTER TABLE organizations ADD COLUMN control_preference VARCHAR(20);
ALTER TABLE organizations ADD COLUMN industry_focus TEXT[];
-- Credit fields
ALTER TABLE organizations ADD COLUMN credit_strategies TEXT[];
-- Multi-strategy fields
ALTER TABLE organizations ADD COLUMN investment_styles TEXT[];
ALTER TABLE organizations ADD COLUMN asset_classes TEXT[];
-- Public markets fields
ALTER TABLE organizations ADD COLUMN trading_strategies TEXT[];
```

## Mapping Current org_type to New System

| Current org_type | New Category | New Type | Profile Style |
|------------------|--------------|----------|---------------|
| investment_firm | investment_firm | vc (default) | vc_style |
| company | company | corp | null |
| law_firm | service_provider | law_firm | null |
| bank | company | bank | null |
| accelerator | investment_firm | accelerator | vc_style |
| other | other | (create as needed) | null |

## Files to Create

**Models:**
- `app/models/organization_category.py`
- `app/models/organization_type.py`
- `app/models/investment_profile_option.py`

**Routers:**
- `app/routers/lookups.py`
- `app/routers/admin/organization_types.py`

**Templates:**
- `app/templates/organizations/sections/_investment_profile_pe.html`
- `app/templates/organizations/sections/_investment_profile_credit.html`
- `app/templates/organizations/sections/_investment_profile_multi.html`
- `app/templates/organizations/sections/_investment_profile_public.html`
- `app/templates/settings/organization_types.html`

**Migrations:**
- `alembic/versions/xxx_create_org_type_lookup_tables.py`
- `alembic/versions/xxx_add_org_profile_fields.py`
- `alembic/versions/xxx_seed_org_types.py`
- `alembic/versions/xxx_backfill_org_categories.py`

## Dev Environment

```powershell
docker start blackbook-db
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

## Estimated Total Effort

~28-42 hours across all phases

## Important Notes

1. Keep the existing `org_type` enum column temporarily for backward compatibility
2. After migration verified, can deprecate `org_type` in favor of `category_id`/`type_id`
3. Investment Profile section visibility: check `category.has_investment_profile`
4. Profile fields shown: check `type.profile_style`
5. Admin UI should prevent deleting types that have organizations using them
