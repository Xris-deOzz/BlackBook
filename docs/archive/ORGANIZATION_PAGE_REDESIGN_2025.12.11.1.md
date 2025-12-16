# Organization Page Redesign - Implementation Specification
**Version: 2025.12.11.1**
**Project: Perun's BlackBook CRM**
**Status: ✅ COMPLETED (December 11, 2025)**

---

## IMPLEMENTATION COMPLETION STATUS

### Phase A: Database & Models ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| A1 - Alembic migrations | ✅ | Tables created and migrated |
| A2 - SQLAlchemy models | ✅ | `OrganizationOffice`, `OrganizationRelationship`, `OrganizationRelationshipStatus` |
| A3 - Organization model updates | ✅ | Investment profile fields added |
| A4 - Seed relationship types | ✅ | Via `OrgRelationshipType` enum |
| A5 - Migration testing | ✅ | Verified in dev |

### Phase B: API Endpoints ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| B1 - Pydantic schemas | ✅ | In router files |
| B2 - CRUD for offices | ✅ | `POST/DELETE /api/organizations/{id}/offices` |
| B3 - CRUD for org relationships | ✅ | Via `organizations.py` router |
| B4 - Relationship status endpoints | ✅ | `GET/PUT /sections/relationship-status` |
| B5 - Aggregated interactions | ✅ | Via `organization_details.py` |
| B6 - Logo upload | ✅ | Implemented |
| B7 - Enhanced GET endpoint | ✅ | All relations loaded |
| B8 - Lookup endpoints | ⚠️ | Hardcoded in templates |

### Phase C: Frontend View Page ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| C1 - Investment Profile section | ✅ | Collapsible, conditional for VC/PE |
| C2 - Office Locations section | ✅ | View + inline edit |
| C3 - Links section | ✅ | Website, Crunchbase with icons |
| C4 - My Relationship Status | ✅ | Sidebar card with warmth, contacts |
| C5 - Affiliated People titles | ✅ | Shows role/title from employment |
| C6 - Related Organizations | ✅ | Grouped by relationship type |
| C7 - Interaction History | ✅ | Aggregated across org people |
| C8 - Logo display | ✅ | With upload and zoom modal |

### Phase D: Frontend Edit Page ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| D1 - Investment Profile edit | ✅ | Multi-select stages/sectors |
| D2 - Office Locations edit | ✅ | Add/delete with HTMX |
| D3 - Links edit | ✅ | Inline editing |
| D4 - Relationship Status edit | ✅ | Person lookup, warmth select |
| D5 - Related Organizations | ✅ | Add relationship modal |
| D6 - Logo upload | ✅ | Drag-and-drop support |

### Phase E: Testing & Polish ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| E1 - Bidirectional relationships | ✅ | Auto-creates inverse |
| E2 - Interaction aggregation | ✅ | Via person employment |
| E3 - Investment profile conditional | ✅ | Shows for investment_firm type |
| E4 - Responsive design | ✅ | 2-column layout |

### UI Polish (December 11, 2025)
- ✅ Office Locations moved to bottom of left column
- ✅ Button colors unified (AI Research, Delete → blackbook-100/700)
- ✅ Org Type badge moved to Tags row

### Files Created/Modified

**Models:**
- `app/models/organization_office.py` - Office locations model
- `app/models/org_relationship.py` - Org-to-org relationship model
- `app/models/organization_relationship_status.py` - Your relationship with org

**Routers:**
- `app/routers/organization_sections.py` - HTMX section editing API
- `app/routers/organization_details.py` - Detail view endpoints
- `app/routers/organizations.py` - Updated with relationship endpoints

**Templates:**
- `app/templates/organizations/detail.html` - Redesigned view page
- `app/templates/organizations/edit.html` - Enhanced edit page
- `app/templates/organizations/sections/` - All inline-edit partials:
  - `_description_view.html`, `_description_edit.html`
  - `_notes_view.html`, `_notes_edit.html`
  - `_links_view.html`, `_links_edit.html`
  - `_investment_profile_view.html`, `_investment_profile_edit.html`
  - `_offices_view.html`, `_offices_edit.html`
  - `_relationship_status_view.html`, `_relationship_status_edit.html`
  - `_people_view.html`
  - `_related_orgs_view.html`
  - `_interaction_history_view.html`

---

## Project Context

Perun's BlackBook is a self-hosted personal CRM built with:
- **Backend:** Python 3.11, FastAPI, PostgreSQL
- **Frontend:** HTMX, TailwindCSS
- **Hosting:** Synology DS220+ via Docker

This document specifies the redesign of the Organization pages (View, Edit, Add) to provide comprehensive tracking for investment firms, companies, and professional relationships.

---

## 1. OVERVIEW OF CHANGES

### Pages Affected
1. **Organization View Page** - Display organization details
2. **Organization Edit Page** - Edit existing organization
3. **Add Organization Page** - Create new organization

### Key Requirements
- All sections must be **collapsible** (consistent with Person page)
- Support for **Investment Firms** (VC, PE) with investment profile fields
- Enhanced **Related Organizations** with relationship types
- **Interaction History** aggregated across all affiliated people
- **Relationship Status** tracking for the organization overall
- Show **titles/roles** for affiliated people

---

## 2. PAGE LAYOUT STRUCTURE

### Main Content Area (Left ~70%)

| Order | Section | Description |
|-------|---------|-------------|
| 1 | Header | Logo, name, type, tags, action buttons |
| 2 | Description | About the organization |
| 3 | Investment Profile | Stage, check size, sectors, fund info (for VC/PE) |
| 4 | Office Locations | HQ and other office addresses |
| 5 | Affiliated People | People with roles/titles shown |
| 6 | Related Organizations | Portfolio, Co-Investors, Parent/Sub, LPs |
| 7 | Interaction History | Aggregated interactions with anyone at org |
| 8 | Notes | Free-form notes |

### Sidebar (Right ~30%)

| Order | Section |
|-------|---------|
| 1 | Links (Website, LinkedIn, Twitter, Crunchbase, PitchBook, AngelList) |
| 2 | My Relationship Status (Primary Contact, Warmth, Intro Via, Last Meeting, Next Follow-up) |
| 3 | Summary (People count, Tags count, Interactions count) |
| 4 | Record Info |

---

## 3. DATABASE SCHEMA CHANGES

### 3.1 New Tables to Create

```sql
-- Organization Offices (multiple locations per org)
CREATE TABLE organization_offices (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    office_type VARCHAR(50) NOT NULL,  -- 'headquarters', 'regional', 'satellite'
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    address VARCHAR(255),
    is_headquarters BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_org_offices_org_id ON organization_offices(organization_id);

-- Organization Relationships (org-to-org)
CREATE TABLE organization_relationships (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    related_organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- 'portfolio_company', 'co_investor', 'parent', 'subsidiary', 'limited_partner'
    investment_year INTEGER,  -- For portfolio companies
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, related_organization_id, relationship_type)
);
CREATE INDEX idx_org_rel_org_id ON organization_relationships(organization_id);
CREATE INDEX idx_org_rel_related_id ON organization_relationships(related_organization_id);

-- Organization Relationship Status (your relationship with the org)
CREATE TABLE organization_relationship_status (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    primary_contact_id INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    relationship_warmth VARCHAR(20),  -- 'hot', 'warm', 'met_once', 'cold', 'unknown'
    intro_available_via_id INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    next_followup_date DATE,
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_org_rel_status_org_id ON organization_relationship_status(organization_id);

-- Organization Relationship Types (lookup table)
CREATE TABLE organization_relationship_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    inverse_name VARCHAR(100),  -- For bidirectional display
    description VARCHAR(255),
    is_system BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default organization relationship types
INSERT INTO organization_relationship_types (name, inverse_name, description, is_system) VALUES
    ('portfolio_company', 'investor', 'Company in investment portfolio', TRUE),
    ('investor', 'portfolio_company', 'Investor in this company', TRUE),
    ('co_investor', 'co_investor', 'Frequently co-invests with', TRUE),
    ('parent', 'subsidiary', 'Parent company', TRUE),
    ('subsidiary', 'parent', 'Subsidiary of', TRUE),
    ('limited_partner', 'fund_manager', 'LP in this fund', TRUE),
    ('fund_manager', 'limited_partner', 'Manages fund for this LP', TRUE),
    ('partner', 'partner', 'Strategic partner', TRUE),
    ('competitor', 'competitor', 'Competitor', TRUE),
    ('acquirer', 'acquired', 'Acquired this company', TRUE),
    ('acquired', 'acquirer', 'Was acquired by', TRUE);
```

### 3.2 Modify Existing Tables

```sql
-- Add new columns to organizations table
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_path VARCHAR(500);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS twitter_url VARCHAR(500);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS crunchbase_url VARCHAR(500);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS pitchbook_url VARCHAR(500);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS angellist_url VARCHAR(500);

-- Investment Profile fields (for VC/PE firms)
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS investment_stages VARCHAR(255);  -- JSON array or comma-separated
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS check_size_min INTEGER;  -- In thousands
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS check_size_max INTEGER;  -- In thousands
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS investment_sectors VARCHAR(500);  -- JSON array or comma-separated
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS geographic_focus VARCHAR(255);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS fund_size INTEGER;  -- In millions
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_fund_name VARCHAR(100);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS current_fund_year INTEGER;
```

### 3.3 Relationship Warmth Enum

```sql
-- Warmth levels for relationship tracking
-- 'hot' = Active deal/discussion
-- 'warm' = Regular contact, good relationship
-- 'met_once' = Had one meeting/interaction
-- 'cold' = No recent contact or new relationship
-- 'unknown' = Haven't assessed yet
```

---

## 4. FIELD SPECIFICATIONS

### 4.1 Investment Profile Section (for VC/PE/Investment Firms)

| Field | Type | Options/Format | Notes |
|-------|------|----------------|-------|
| Investment Stages | Multi-select | Pre-Seed, Seed, Series A, Series B, Growth, Late Stage, Buyout | Which stages they invest in |
| Check Size Range | Currency range | Min-Max in $K or $M | Typical investment size |
| Investment Sectors | Multi-select + Custom | SaaS, Fintech, Healthcare, Consumer, Enterprise, AI/ML, etc. | Sectors/thesis |
| Geographic Focus | Multi-select | US, Europe, Asia, Global, Specific regions | Where they invest |
| Fund Size | Currency | In $M | AUM or fund size |
| Current Fund | Text + Year | "Fund IV (2023)" | Latest fund info |

### 4.2 Office Locations Section

| Field | Type | Notes |
|-------|------|-------|
| City | Text | Required |
| State/Region | Text | Optional |
| Country | Text | Required |
| Address | Text | Optional, full street address |
| Is Headquarters | Boolean | Mark one as HQ |

**Max entries:** 5 offices per organization

### 4.3 Social & Web Links

| Field | Type | Icon |
|-------|------|------|
| Website | URL | 🌐 |
| LinkedIn | URL | LinkedIn icon |
| Twitter/X | URL | X icon |
| Crunchbase | URL | CB icon |
| PitchBook | URL | PB icon |
| AngelList | URL | AL icon |

### 4.4 My Relationship Status

| Field | Type | Notes |
|-------|------|-------|
| Primary Contact | Person lookup | Main person I deal with |
| Relationship Warmth | Select | 🔥 Hot, 🟢 Warm, 🟡 Met Once, 🔴 Cold, ⚪ Unknown |
| Intro Available Via | Person lookup | Who can introduce me |
| Last Meeting | Auto-calculated | From interactions |
| Next Follow-up | Date picker | When to reach out |

### 4.5 Related Organizations

| Relationship Type | Description | Inverse |
|-------------------|-------------|---------|
| Portfolio Company | Company they invested in | Investor |
| Investor | Firm that invested in them | Portfolio Company |
| Co-Investor | Firms they frequently co-invest with | Co-Investor |
| Parent | Parent company | Subsidiary |
| Subsidiary | Owned by parent | Parent |
| Limited Partner | LP in their fund | Fund Manager |
| Partner | Strategic partner | Partner |

**Additional fields per relationship:**
- Investment Year (for Portfolio/Investor)
- Notes

### 4.6 Affiliated People (Enhanced Display)

Show for each person:
- Avatar/Initials
- Full Name (clickable link)
- **Title/Role at this org** ← New
- Current/Former badge
- Quick actions (view, remove)

---

## 5. API ENDPOINTS

### Organization Offices
- `GET /api/organizations/{id}/offices`
- `POST /api/organizations/{id}/offices`
- `PUT /api/organizations/{id}/offices/{office_id}`
- `DELETE /api/organizations/{id}/offices/{office_id}`

### Organization Relationships
- `GET /api/organizations/{id}/relationships`
- `POST /api/organizations/{id}/relationships` - Creates bidirectional
- `PUT /api/organizations/{id}/relationships/{rel_id}`
- `DELETE /api/organizations/{id}/relationships/{rel_id}` - Deletes both directions

### Relationship Status
- `GET /api/organizations/{id}/relationship-status`
- `PUT /api/organizations/{id}/relationship-status`

### Interaction History (Aggregated)
- `GET /api/organizations/{id}/interactions` - Returns all interactions with any person at org

### Logo Upload
- `POST /api/organizations/{id}/logo`
- `DELETE /api/organizations/{id}/logo`

### Lookups
- `GET /api/organization-relationship-types`
- `GET /api/investment-stages`
- `GET /api/investment-sectors`

---

## 6. INTERACTION HISTORY AGGREGATION

### Logic
1. Get all persons affiliated with this organization
2. Get all interactions for those persons
3. Display chronologically with person name
4. Calculate "Last Contacted" as most recent interaction date

### Display Format
```
Dec 5, 2024 - Meeting with Fred Wilson
Nov 20, 2024 - Email from Brad Burnham  
Oct 15, 2024 - Call with Rebecca Kaden
```

### Summary Stats
- Total interactions: 15
- Last contacted: Dec 5, 2024
- Most frequent contact: Fred Wilson (8 interactions)

---

## 7. FILE ORGANIZATION

```
app/
├── models/
│   ├── organization.py (updated - new fields)
│   ├── organization_office.py (new)
│   ├── organization_relationship.py (new)
│   ├── organization_relationship_status.py (new)
│   └── organization_relationship_type.py (new)
├── schemas/
│   ├── organization_office.py (new)
│   ├── organization_relationship.py (new)
│   └── organization_relationship_status.py (new)
├── routers/
│   ├── organizations.py (updated)
│   └── organization_details.py (new - like person_details.py)
└── templates/
    └── organizations/
        ├── detail.html (updated)
        ├── edit.html (updated)
        ├── new.html (updated)
        └── sections/
            ├── _investment_profile.html (new)
            ├── _offices.html (new)
            ├── _affiliated_people.html (updated - show titles)
            ├── _related_orgs.html (updated)
            ├── _interaction_history.html (new)
            └── _relationship_status.html (new)
```

---

## 8. IMPLEMENTATION TASK LIST

### Phase A: Database & Models (Est: 6 hours)

| Task | Description | Priority |
|------|-------------|----------|
| A1 | Create Alembic migration for new tables and columns | High |
| A2 | Create SQLAlchemy models for new entities | High |
| A3 | Update Organization model with new fields | High |
| A4 | Seed organization_relationship_types | High |
| A5 | Test migrations on dev database | High |

### Phase B: API Endpoints (Est: 8 hours)

| Task | Description | Priority |
|------|-------------|----------|
| B1 | Create Pydantic schemas for new entities | High |
| B2 | Implement CRUD for organization_offices | High |
| B3 | Implement CRUD for organization_relationships (bidirectional) | High |
| B4 | Implement organization_relationship_status endpoints | High |
| B5 | Implement aggregated interactions endpoint | High |
| B6 | Implement logo upload/delete | Medium |
| B7 | Update GET /organizations/{id} to include all new relations | High |
| B8 | Create lookup endpoints | Medium |

### Phase C: Frontend - View Page (Est: 8 hours)

| Task | Description | Priority |
|------|-------------|----------|
| C1 | Add Investment Profile section (collapsible) | High |
| C2 | Add Office Locations section | Medium |
| C3 | Enhance Links section with social icons | Medium |
| C4 | Add Relationship Status card to sidebar | High |
| C5 | Update Affiliated People to show titles | High |
| C6 | Enhance Related Organizations with types | High |
| C7 | Add Interaction History section | High |
| C8 | Add logo display and upload | Medium |

### Phase D: Frontend - Edit Page (Est: 6 hours)

| Task | Description | Priority |
|------|-------------|----------|
| D1 | Investment Profile edit form | High |
| D2 | Office Locations multi-entry form | Medium |
| D3 | Social links edit form | Medium |
| D4 | Relationship Status edit form | High |
| D5 | Related Organizations modal with type selection | High |
| D6 | Logo upload component | Medium |

### Phase E: Testing & Polish (Est: 4 hours)

| Task | Description | Priority |
|------|-------------|----------|
| E1 | Test bidirectional org relationships | High |
| E2 | Test interaction aggregation | High |
| E3 | Test investment profile for different org types | Medium |
| E4 | Responsive design adjustments | Low |

---

## 9. ESTIMATED TOTAL EFFORT

| Phase | Hours |
|-------|-------|
| A: Database & Models | 6 |
| B: API Endpoints | 8 |
| C: Frontend - View Page | 8 |
| D: Frontend - Edit Page | 6 |
| E: Testing & Polish | 4 |
| **Total** | **32 hours** |

---

## 10. UI MOCKUP - VIEW PAGE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ < Back to Organizations                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ [LOGO]  Union Square Ventures          [Investment Firm] [AI Research]       │
│         VC                                               [Edit All] [Delete] │
│         [VC] [NYC]                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────────┐ │
│ │ ▼ Description                    [Edit] │  │ Links                [Edit]│ │
│ │                                         │  │ 🌐 www.usv.com             │ │
│ │ We are a small collegial partnership... │  │ in LinkedIn                │ │
│ │                                         │  │ 𝕏  Twitter                 │ │
│ └─────────────────────────────────────────┘  │ CB Crunchbase              │ │
│                                              └────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐                                 │
│ │ ▼ Investment Profile             [Edit] │  ┌────────────────────────────┐ │
│ │                                         │  │ My Relationship     [Edit] │ │
│ │ Stages: Seed, Series A, Growth          │  │                            │ │
│ │ Check Size: $1M - $20M                  │  │ Primary: Fred Wilson       │ │
│ │ Sectors: Internet, Mobile, SaaS         │  │ Warmth: 🟢 Warm            │ │
│ │ Focus: US, Europe                       │  │ Intro via: —               │ │
│ │ Fund: $1B across 6 funds                │  │ Last contact: Dec 5, 2024  │ │
│ │ Current: Fund VI (2023)                 │  │ Follow-up: Jan 15, 2025    │ │
│ └─────────────────────────────────────────┘  └────────────────────────────┘ │
│                                                                              │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────────┐ │
│ │ ▼ Offices                        [Edit] │  │ Summary                    │ │
│ │                                         │  │ People: 3                  │ │
│ │ 🏢 New York, NY (HQ)                    │  │ Portfolio: 45              │ │
│ │    915 Broadway                         │  │ Interactions: 15           │ │
│ │ 🏢 San Francisco, CA                    │  │ Tags: 2                    │ │
│ └─────────────────────────────────────────┘  └────────────────────────────┘ │
│                                                                              │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────────┐ │
│ │ ▼ Affiliated People              [Edit] │  │ Record Info                │ │
│ │                                         │  │ Created: Dec 7, 2024       │ │
│ │ [FW] Fred Wilson                        │  │ Updated: Dec 11, 2024      │ │
│ │      Managing Partner        [Current]  │  │ ID: baf5d...              │ │
│ │ [BB] Brad Burnham                       │  └────────────────────────────┘ │
│ │      Partner                 [Current]  │                                 │
│ │ [RK] Rebecca Kaden                      │                                 │
│ │      Partner                 [Current]  │                                 │
│ └─────────────────────────────────────────┘                                 │
│                                                                              │
│ ┌─────────────────────────────────────────┐                                 │
│ │ ▼ Related Organizations          [Edit] │                                 │
│ │                                         │                                 │
│ │ Portfolio Companies (45)                │                                 │
│ │   Twitter (2007) • Tumblr (2007)        │                                 │
│ │   Coinbase (2013) • MongoDB (2013)      │                                 │
│ │   [Show all...]                         │                                 │
│ │                                         │                                 │
│ │ Co-Investors (8)                        │                                 │
│ │   Andreessen Horowitz • Sequoia         │                                 │
│ └─────────────────────────────────────────┘                                 │
│                                                                              │
│ ┌─────────────────────────────────────────┐                                 │
│ │ ▼ Interaction History            [View] │                                 │
│ │                                         │                                 │
│ │ Dec 5, 2024 - Meeting with Fred Wilson  │                                 │
│ │ Nov 20, 2024 - Email from Brad Burnham  │                                 │
│ │ Oct 15, 2024 - Call with Rebecca Kaden  │                                 │
│ │ [Show all 15 interactions...]           │                                 │
│ └─────────────────────────────────────────┘                                 │
│                                                                              │
│ ┌─────────────────────────────────────────┐                                 │
│ │ ▼ Notes                          [Edit] │                                 │
│ │                                         │                                 │
│ │ No notes                                │                                 │
│ └─────────────────────────────────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. CONDITIONALLY SHOW INVESTMENT PROFILE

The Investment Profile section should only appear for organization types that are investment-related:

**Show Investment Profile for:**
- VC (Venture Capital)
- PE (Private Equity)
- Investment Firm
- Family Office
- Angel Group
- Hedge Fund

**Hide Investment Profile for:**
- Company
- Startup
- Law Firm
- Bank
- Consulting
- Other

This can be controlled by checking `organization.type` or `organization.category`.

---

## 12. KEY IMPLEMENTATION NOTES

1. **Bidirectional org relationships** - When USV → Twitter (portfolio_company), auto-create Twitter → USV (investor)
2. **Investment Profile conditional** - Only show for VC/PE/Investment firm types
3. **Interaction aggregation** - Query all persons at org, then all their interactions
4. **Titles in Affiliated People** - Already stored in person_employment.title, just need to display
5. **Relationship warmth** - Visual indicators with colors/emojis
6. **Logo upload** - Same pattern as person profile pictures

---

*End of Specification Document*
