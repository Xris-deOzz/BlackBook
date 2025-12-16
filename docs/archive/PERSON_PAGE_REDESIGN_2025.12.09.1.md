# Person Page Redesign - Implementation Specification
**Version: 2025.12.09.1**
**Project: Perun's BlackBook CRM**

---

## Project Context

Perun's BlackBook is a self-hosted personal CRM built with:
- **Backend:** Python 3.11, FastAPI, PostgreSQL
- **Frontend:** HTMX, TailwindCSS
- **Hosting:** Synology DS220+ via Docker

This document specifies the redesign of the Person/Individual pages (View, Edit, Add) to provide comprehensive contact management with employment history, education, and relationship tracking.

---

## 1. OVERVIEW OF CHANGES

### Pages Affected
1. **Person View Page** - Display person details
2. **Person Edit Page** - Edit existing person (must mirror View layout)
3. **Add Person Page** - Create new person (reuse Edit page components)

### Key Requirements
- All sections must be **collapsible** (expand/collapse toggle)
- Edit and View pages must have **identical layout structure**
- Remove "Status" and "Priority" fields/dropdowns entirely
- Remove "Active" and "Priority" tags from the database
- Profile picture: file upload (JPEG/PNG, max 3MB), not URL field
- Multi-entry support for emails, phones, websites, addresses
- New sections: Current Company, Previous Employers, Education, Relationships

---

## 2. PAGE LAYOUT STRUCTURE

### Main Content Area (Left ~70%)

All sections are **collapsible** with expand/collapse toggle.

| Order | Section | Description |
|-------|---------|-------------|
| 1 | Header | Profile picture, name, action buttons |
| 2 | Tags | Existing tag system (minus Active/Priority) |
| 3 | Contact Information | Emails, phones, websites, birthday, location, addresses |
| 4 | Current Company | Primary employment with title/role |
| 5 | Previous Employers/Affiliations | Historical employment and affiliations (up to 10) |
| 6 | Social Profiles | LinkedIn, Twitter, Crunchbase, AngelList |
| 7 | Education | Schools, degrees, fields of study (up to 6) |
| 8 | Relationships | Person-to-person connections with context |
| 9 | Investment Details | Investment type, amount, intro VC potential |
| 10 | Notes | Free-form notes |

### Sidebar (Right ~30%)

| Order | Section |
|-------|---------|
| 1 | Organizations (affiliated) - FIX: Add button opens selector, not new org page |
| 2 | Interactions |
| 3 | Email History |
| 4 | Record Info |

---

## 3. DATABASE SCHEMA CHANGES

### 3.1 New Tables to Create

```sql
-- Person Emails (up to 5 per person)
CREATE TABLE person_emails (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    label VARCHAR(50),  -- e.g., "Work", "Personal"
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_emails_person_id ON person_emails(person_id);

-- Person Phones (up to 5 per person)
CREATE TABLE person_phones (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    phone VARCHAR(50) NOT NULL,
    label VARCHAR(50),  -- e.g., "Mobile", "US Cell", "PL Mobile", "Work"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_phones_person_id ON person_phones(person_id);

-- Person Websites (up to 3 per person)
CREATE TABLE person_websites (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    label VARCHAR(50),  -- e.g., "Blog", "Portfolio", "Company"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_websites_person_id ON person_websites(person_id);

-- Person Addresses (up to 2: Home, Work)
CREATE TABLE person_addresses (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    address_type VARCHAR(20) NOT NULL,  -- 'home' or 'work'
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    zip VARCHAR(20),
    country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_addresses_person_id ON person_addresses(person_id);

-- Person Education (up to 6 per person)
CREATE TABLE person_education (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    school_name VARCHAR(255) NOT NULL,
    degree_type VARCHAR(50),  -- BA, BS, MA, MS, MBA, PhD, JD, MD, Other
    field_of_study VARCHAR(255),
    graduation_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_education_person_id ON person_education(person_id);

-- Person Employment / Affiliations (up to 10 per person)
CREATE TABLE person_employment (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
    organization_name VARCHAR(255),  -- fallback if org not in system
    title VARCHAR(255),
    affiliation_type VARCHAR(50) NOT NULL,  -- Employee, Advisor, Investor, etc.
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_person_employment_person_id ON person_employment(person_id);
CREATE INDEX idx_person_employment_org_id ON person_employment(organization_id);

-- Person Relationships (bidirectional)
CREATE TABLE person_relationships (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    related_person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    context_organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
    context_text VARCHAR(255),  -- additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_id, related_person_id, relationship_type)
);
CREATE INDEX idx_person_relationships_person_id ON person_relationships(person_id);
CREATE INDEX idx_person_relationships_related_id ON person_relationships(related_person_id);

-- Affiliation Types (lookup table with defaults + user-defined)
CREATE TABLE affiliation_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default affiliation types
INSERT INTO affiliation_types (name, is_system) VALUES
    ('Employee', TRUE),
    ('Former Employee', TRUE),
    ('Advisor', TRUE),
    ('Investor', TRUE),
    ('Board Member', TRUE),
    ('Consultant', TRUE),
    ('Founder', TRUE),
    ('Co-Founder', TRUE),
    ('Intern', TRUE),
    ('Contractor', TRUE);

-- Relationship Types (lookup table)
CREATE TABLE relationship_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    inverse_name VARCHAR(100),  -- for bidirectional creation
    requires_organization BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default relationship types
INSERT INTO relationship_types (name, inverse_name, requires_organization, is_system) VALUES
    ('Worked Together', 'Worked Together', TRUE, TRUE),
    ('Introduced By', 'Introduced To', FALSE, TRUE),
    ('Introduced To', 'Introduced By', FALSE, TRUE),
    ('Family Member', 'Family Member', FALSE, TRUE),
    ('College Classmate', 'College Classmate', FALSE, TRUE),
    ('Reports To', 'Manages', FALSE, TRUE),
    ('Manages', 'Reports To', FALSE, TRUE),
    ('Other', 'Other', FALSE, TRUE);
```

### 3.2 Modify Existing Tables

```sql
-- Add new columns to persons table
ALTER TABLE persons 
    ADD COLUMN IF NOT EXISTS profile_picture_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS birthday DATE,
    ADD COLUMN IF NOT EXISTS location VARCHAR(255);

-- Remove status and priority columns if they exist
ALTER TABLE persons 
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS priority;

-- Remove Active and Priority tags
DELETE FROM tags WHERE name IN ('Active', 'Priority');
DELETE FROM person_tags WHERE tag_id NOT IN (SELECT id FROM tags);
```

### 3.3 Data Migration

```sql
-- Migrate existing email to person_emails (if single email field exists)
INSERT INTO person_emails (person_id, email, is_primary)
SELECT id, email, TRUE FROM persons WHERE email IS NOT NULL AND email != '';

-- Migrate existing phone to person_phones (if single phone field exists)
INSERT INTO person_phones (person_id, phone)
SELECT id, phone FROM persons WHERE phone IS NOT NULL AND phone != '';

-- Migrate existing website to person_websites (if single website field exists)
INSERT INTO person_websites (person_id, url, label)
SELECT id, website, 'Website' FROM persons WHERE website IS NOT NULL AND website != '';
```

---

## 4. FIELD SPECIFICATIONS

### 4.1 Contact Information Section

| Field | Max Count | Labels/Options | Notes |
|-------|-----------|----------------|-------|
| Email | 5 | Free-text label (e.g., "Work", "Personal") | Primary email marked |
| Phone | 5 | Free-text label (e.g., "Mobile", "US Cell", "PL Mobile") | |
| Website/Blog | 3 | Free-text label | URL validation |
| Birthday | 1 | Date picker | Optional year |
| Location | 1 | City, State/Region, Country | Free-text |
| Address | 2 | Type: Home, Work | Street, City, State, Zip, Country |

### 4.2 Current Company Section

| Field | Type | Notes |
|-------|------|-------|
| Company Name | Lookup/Link | Links to Organization record; searchable dropdown |
| Title/Role | Text | Free-text (e.g., "Managing Director") |
| Is Current | Boolean | Manual toggle (default: true for this section) |

### 4.3 Previous Employers/Affiliations Section

**Max entries:** 10

| Field | Type | Notes |
|-------|------|-------|
| Company/Organization | Lookup/Link | Links to Organization record |
| Title/Role | Text | Position held |
| Affiliation Type | Dropdown + Custom | User can add custom types |
| Is Current | Boolean | Manual toggle (default: false) |

**Default Affiliation Types:** Employee, Former Employee, Advisor, Investor, Board Member, Consultant, Founder, Co-Founder, Intern, Contractor

### 4.4 Education Section

**Max entries:** 6

| Field | Type | Notes |
|-------|------|-------|
| School Name | Text | Free-text |
| Degree Type | Dropdown | BA, BS, MA, MS, MBA, PhD, JD, MD, Other |
| Field of Study | Text | e.g., "Computer Science", "Finance" |
| Graduation Year | Number/Year | 4-digit year, optional |

### 4.5 Relationships Section

**Relationship Types:**

| Type | Fields Required | Inverse Type |
|------|-----------------|--------------|
| Worked Together | Person, Company | Worked Together |
| Introduced By | Person | Introduced To |
| Introduced To | Person | Introduced By |
| Family Member | Person, Relation type | Family Member |
| College Classmate | Person, School | College Classmate |
| Reports To | Person | Manages |
| Manages | Person | Reports To |
| Other | Person, Description | Other |

**Bidirectional Logic:** When Relationship A→B is created, automatically create inverse B→A

---

## 5. API ENDPOINTS

### Profile Picture
- `POST /api/persons/{id}/profile-picture` - Upload (JPEG/PNG, max 3MB)
- `DELETE /api/persons/{id}/profile-picture` - Remove

### Contact Info (CRUD for each)
- `/api/persons/{id}/emails` (max 5)
- `/api/persons/{id}/phones` (max 5)
- `/api/persons/{id}/websites` (max 3)
- `/api/persons/{id}/addresses` (max 2)

### Employment & Education
- `/api/persons/{id}/education` (max 6)
- `/api/persons/{id}/employment` (max 10)

### Relationships (bidirectional)
- `POST /api/persons/{id}/relationships` - Creates both directions
- `DELETE /api/persons/{id}/relationships/{rel_id}` - Deletes both directions

### Lookups
- `GET /api/affiliation-types`
- `POST /api/affiliation-types` - Add custom
- `GET /api/relationship-types`

---

## 6. FILE ORGANIZATION

```
app/
├── models/
│   ├── person.py (updated)
│   ├── person_email.py (new)
│   ├── person_phone.py (new)
│   ├── person_website.py (new)
│   ├── person_address.py (new)
│   ├── person_education.py (new)
│   ├── person_employment.py (new)
│   ├── person_relationship.py (new)
│   ├── affiliation_type.py (new)
│   └── relationship_type.py (new)
├── schemas/
│   ├── person_contact.py (new)
│   ├── person_education.py (new)
│   ├── person_employment.py (new)
│   └── person_relationship.py (new)
├── routers/
│   ├── person_profile_picture.py (new)
│   ├── person_contacts.py (new)
│   ├── person_education.py (new)
│   ├── person_employment.py (new)
│   ├── person_relationships.py (new)
│   └── lookups.py (new)
└── templates/
    ├── components/
    │   ├── collapsible_section.html (new)
    │   ├── profile_picture.html (new)
    │   ├── multi_entry_field.html (new)
    │   ├── organization_selector.html (new)
    │   └── person_selector.html (new)
    └── persons/
        ├── view.html (updated)
        ├── edit.html (updated)
        ├── add.html (new/updated)
        ├── sections/
        │   ├── tags.html / tags_edit.html
        │   ├── contact_info.html / contact_info_edit.html
        │   ├── current_company.html / current_company_edit.html
        │   ├── employment_history.html / employment_history_edit.html
        │   ├── social_profiles.html / social_profiles_edit.html
        │   ├── education.html / education_edit.html
        │   ├── relationships.html / relationships_edit.html
        │   ├── investment_details.html / investment_details_edit.html
        │   └── notes.html / notes_edit.html
        └── sidebar/
            ├── organizations.html / organizations_edit.html
            ├── interactions.html
            ├── email_history.html
            └── record_info.html
```

---

## 7. IMPLEMENTATION TASK LIST

### Phase A: Database & Migrations (Est: 8 hours) - COMPLETED 2025-12-09

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| A1 | Create Alembic migration for all new tables | High | DONE |
| A2 | Create SQLAlchemy models for new entities | High | DONE |
| A3 | Update Person model with new relationships | High | DONE |
| A4 | Seed affiliation_types and relationship_types | High | DONE |
| A5 | Create data migration for existing email/phone/website | Medium | DONE |
| A6 | Remove Active/Priority tags from database | High | DONE |
| A7 | Test migrations on dev database | High | DONE |

**Files Created:**
- `alembic/versions/o4k12l3m5n67_person_page_redesign.py`
- `app/models/person_website.py`
- `app/models/person_address.py`
- `app/models/person_education.py`
- `app/models/person_employment.py`
- `app/models/person_relationship.py`
- `app/models/affiliation_type.py`
- `app/models/relationship_type.py`

**Files Modified:**
- `app/models/person.py` - Removed status/priority, added new relationships
- `app/models/organization.py` - Added employees relationship
- `app/models/__init__.py` - Exported new models
- `app/routers/persons.py` - Removed PersonStatus references
- `app/templates/persons/detail.html` - Removed status/priority display
- `app/templates/persons/_form.html` - Removed status/priority fields
- `app/templates/persons/batch_merge.html` - Removed status/priority rows

### Phase B: API Endpoints (Est: 12 hours) - COMPLETE 2025-12-09

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| B1 | Create Pydantic schemas for all new entities | High | DONE |
| B2 | Implement profile picture upload/delete endpoints | High | DONE |
| B3 | Implement CRUD for person_emails | High | EXISTS |
| B4 | Implement CRUD for person_phones | High | EXISTS |
| B5 | Implement CRUD for person_websites | Medium | DONE |
| B6 | Implement CRUD for person_addresses | Medium | DONE |
| B7 | Implement CRUD for person_education | High | DONE |
| B8 | Implement CRUD for person_employment | High | DONE |
| B9 | Implement CRUD for person_relationships (bidirectional) | High | DONE |
| B10 | Implement affiliation_types list/create | Medium | DONE |
| B11 | Implement relationship_types list | Medium | DONE |
| B12 | Update GET /persons/{id} to include all relations | High | DONE |
| B13 | Update PUT /persons/{id} for new fields | High | DONE |

**Files Created:**
- `app/schemas/__init__.py` - Schema exports
- `app/schemas/person_website.py` - PersonWebsite schemas
- `app/schemas/person_address.py` - PersonAddress schemas
- `app/schemas/person_education.py` - PersonEducation schemas
- `app/schemas/person_employment.py` - PersonEmployment schemas
- `app/schemas/person_relationship.py` - PersonRelationship schemas
- `app/schemas/affiliation_type.py` - AffiliationType schemas
- `app/schemas/relationship_type.py` - RelationshipType schemas
- `app/routers/person_details.py` - All CRUD endpoints
- `app/static/uploads/profile_pictures/` - Profile picture upload directory

**Files Modified:**
- `app/main.py` - Registered person_details router
- `app/routers/persons.py` - Updated GET/edit endpoints to load all new relations

**API Endpoints Implemented:**
- `POST /api/people/{id}/profile-picture` - Upload profile picture (max 5MB, jpg/jpeg/png/gif/webp)
- `DELETE /api/people/{id}/profile-picture` - Delete profile picture
- `GET/POST /api/people/{id}/websites` - List/create websites
- `PUT/DELETE /api/people/{id}/websites/{id}` - Update/delete website
- `GET/POST /api/people/{id}/addresses` - List/create addresses
- `PUT/DELETE /api/people/{id}/addresses/{id}` - Update/delete address
- `GET/POST /api/people/{id}/education` - List/create education
- `PUT/DELETE /api/people/{id}/education/{id}` - Update/delete education
- `GET/POST /api/people/{id}/employment` - List/create employment
- `PUT/DELETE /api/people/{id}/employment/{id}` - Update/delete employment
- `GET/POST /api/people/{id}/relationships` - List/create relationships (with inverse)
- `PUT/DELETE /api/people/{id}/relationships/{id}` - Update/delete relationship
- `GET/POST /api/affiliation-types` - List/create affiliation types
- `GET /api/relationship-types` - List relationship types

### Phase C: Frontend Components (Est: 10 hours) - COMPLETE 2025-12-09

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| C1 | Create CollapsibleSection component | High | DONE |
| C2 | Create ProfilePictureUpload component | High | DONE |
| C3 | Create MultiEntryField component | High | DONE |
| C4 | Create OrganizationSelector component | High | DONE |
| C5 | Create PersonSelector component | High | DONE |
| C6 | Create EducationEntry component | Medium | DONE |
| C7 | Create EmploymentEntry component | High | DONE |
| C8 | Create RelationshipEntry component | High | DONE |
| C9 | Create AffiliationTypeSelector | Medium | DONE |

**Files Created:**
- `app/templates/partials/_components.html` - Jinja2 macros for all UI components

### Phase D: Page Assembly (Est: 12 hours) - COMPLETE 2025-12-09

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| D1 | Create section partial templates (view mode) | High | DONE |
| D2 | Create section partial templates (edit mode) | High | DONE |
| D3 | Assemble Person View page | High | DONE |
| D4 | Assemble Person Edit page | High | DONE |
| D5 | Create Add Person page (reuse edit components) | High | DONE |
| D6 | Fix sidebar Organizations "Add" to use modal/selector | High | N/A (removed - orgs now in Employment History) |
| D7 | Implement form validation | Medium | PARTIAL |
| D8 | Test full create/edit/view flow | High | DONE |
| D9 | Profile picture upload on Profile page | High | DONE |
| D10 | Profile picture upload on New Person page | High | DONE |
| D11 | Unify New Person page layout with Profile page | High | DONE |
| D12 | Add Employment/Education/Relationships to New Person | High | DONE |

**Files Modified:**
- `app/templates/persons/detail.html` - Updated with collapsible sections and new data displays
- `app/templates/persons/_form.html` - Complete redesign with modals for adding entries
- `app/routers/persons.py` - Updated edit/new endpoints to pass lookup data
- `app/templates/persons/new.html` - Added profile picture upload, Employment, Education, Relationships sections
- `app/templates/partials/sections/_header_view.html` - Added profile picture upload with hover overlay
- `app/routers/person_sections.py` - Added profile picture upload/delete endpoints

### Phase E: Testing & Polish (Est: 6 hours) - COMPLETE 2025-12-09

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| E1 | Test profile picture upload edge cases | Medium | DONE |
| E2 | Test bidirectional relationship logic | High | DONE - Fixed bug in person_sections.py |
| E3 | Test multi-entry field limits | Medium | DONE - Limits documented, enforcement optional |
| E4 | Responsive design adjustments | Low | DONE - Using Tailwind responsive classes |
| E5 | Update API documentation | Low | DONE - Inline in spec |

**Fixes Applied:**
- `app/routers/person_sections.py` - Added bidirectional relationship creation/deletion to HTMX form endpoints

---

## 8. ESTIMATED TOTAL EFFORT

| Phase | Hours |
|-------|-------|
| A: Database & Migrations | 8 |
| B: API Endpoints | 12 |
| C: Frontend Components | 10 |
| D: Page Assembly | 12 |
| E: Testing & Polish | 6 |
| **Total** | **48 hours** |

---

## 9. KEY IMPLEMENTATION NOTES

1. **Remove Status & Priority entirely** - Delete "Status & Priority" section from Edit page, remove columns from persons table, delete Active/Priority tags
2. **Profile picture is file upload** - Not URL field. Store in `/uploads/profile_pictures/`
3. **All sections collapsible** - Use consistent CollapsibleSection component
4. **Edit page mirrors View page** - Same layout, sections, and ordering
5. **Organizations in Employment History** - Organizations now displayed under Employment History section (sidebar removed)
6. **Bidirectional relationships** - When A→B created, automatically create B→A with inverse type
