# Perun's BlackBook - Data Mapping Reference

**Document Version:** 2025.12.06.1

This document maps Airtable export fields to the BlackBook database schema.

---

## Source Files

| File | Target Table | Records |
|------|--------------|---------|
| Individuals-All Contacts.csv | `persons` | Primary contacts |
| Firms-All Funds.csv | `organizations` | Investment firms |
| Company-List.csv | `organizations` | Companies |
| Interactions-All Interactions.csv | `interactions` | Interaction log |

---

## Individuals → persons

| Airtable Field | DB Column | Type | Notes |
|----------------|-----------|------|-------|
| First & Last Name | `full_name` | VARCHAR(300) | Also split into first_name/last_name |
| Category | → `person_tags` | Junction | Comma-separated, creates tags |
| Notes | `notes` | TEXT | |
| Title | `title` | VARCHAR(300) | |
| Invest Firm | → `person_organizations` | Junction | Links to org, relationship='affiliated_with' |
| Potential Intro - VC | `potential_intro_vc` | TEXT | |
| Peers | → `person_organizations` | Junction | Links to org, relationship='peer_history' |
| Peers 2 | → `person_organizations` | Junction | Links to org, relationship='peer_history' |
| Priority | `priority` | INTEGER | |
| Contacted? | `contacted` | BOOLEAN | |
| Status | `status` | ENUM | |
| Most Recent Interaction | **SKIP** | - | Calculated field |
| No. of Days Since Last Interaction | **SKIP** | - | Calculated field |
| Interactions | **SKIP** | - | Linked records (handled separately) |
| Investment Type | `investment_type` | VARCHAR(200) | |
| Amount Funded | `amount_funded` | VARCHAR(200) | |
| Tel | `phone` | VARCHAR(100) | |
| Email | `email` | VARCHAR(255) | |
| LinkedIn | `linkedin` | VARCHAR(500) | |
| Crunchbase | `crunchbase` | VARCHAR(500) | |
| Angel List | `angellist` | VARCHAR(500) | |
| Twitter | `twitter` | VARCHAR(500) | |
| Blog / Site | `website` | VARCHAR(500) | |
| Lives-Works Locations | `location` | VARCHAR(300) | |
| Jobs | **SKIP** | - | Not needed |

---

## Firms → organizations

| Airtable Field | DB Column | Type | Notes |
|----------------|-----------|------|-------|
| Name | `name` | VARCHAR(300) | |
| Firm Category | `category` | VARCHAR(200) | Also creates tags |
| Priority Rank | `priority_rank` | INTEGER | |
| Select | `custom_fields.select` | JSONB | |
| Description | `description` | TEXT | |
| Contacts | `custom_fields.contacts_note` | JSONB | Free text about contacts |
| Contacts Note | `custom_fields.contacts_note_2` | JSONB | |
| Website | `website` | VARCHAR(500) | |
| - | `org_type` | ENUM | Set to 'investment_firm' |

---

## Companies → organizations

| Airtable Field | DB Column | Type | Notes |
|----------------|-----------|------|-------|
| Name | `name` | VARCHAR(300) | |
| Description | `description` | TEXT | |
| Category | `category` | VARCHAR(200) | Also creates tags |
| Key People | → `organization_persons` | Junction | relationship='key_person' |
| Fundraising | `custom_fields.fundraising` | JSONB | |
| Latest Stage | `custom_fields.latest_stage` | JSONB | |
| VC invested | `custom_fields.vc_invested` | JSONB | |
| Individuals | → `organization_persons` | Junction | relationship='contact_at' |
| Other People Notes | `custom_fields.other_people_notes` | JSONB | |
| Connections | → `organization_persons` | Junction | relationship='connection' |
| Comments / Log | `notes` | TEXT | |
| Revenue Model | `custom_fields.revenue_model` | JSONB | |
| Crunchbase | `crunchbase` | VARCHAR(500) | |
| Website | `website` | VARCHAR(500) | |
| Peer Location | `custom_fields.peer_location` | JSONB | |
| Job Open 1 | **SKIP** | - | Not needed |
| Applied? | **SKIP** | - | Not needed |
| Job Open 2 | **SKIP** | - | Not needed |
| Applied J2? | **SKIP** | - | Not needed |
| Jobs | **SKIP** | - | Not needed |
| Docs | `custom_fields.docs` | JSONB | |
| - | `org_type` | ENUM | Set to 'company' |

---

## Interactions → interactions

| Airtable Field | DB Column | Type | Notes |
|----------------|-----------|------|-------|
| Name | `airtable_name` | VARCHAR(500) | Original record name |
| Indiv Partner | `person_id` / `person_name` | UUID/VARCHAR | Match to persons table |
| Interaction Medium | `medium` | ENUM | Map to interaction_medium |
| Date of Interaction | `interaction_date` | DATE | Parse MM/DD/YYYY format |
| Notes | `notes` | TEXT | |
| Files Sent | `files_sent` | TEXT | |

### Interaction Medium Mapping

| Airtable Value | DB Enum |
|----------------|---------|
| Meeting | `meeting` |
| Email | `email` |
| LinkedIn | `linkedin` |
| Lunch | `lunch` |
| Call | `call` |
| Coffee | `coffee` |
| (other) | `other` |

---

## Relationship Types

| Type | Source | Description |
|------|--------|-------------|
| `affiliated_with` | Individuals.Invest Firm | Person works at org |
| `peer_history` | Individuals.Peers, Peers 2 | Person has past connection |
| `key_person` | Companies.Key People | Important person at company |
| `connection` | Companies.Connections | Person who can make intros |
| `contact_at` | Companies.Individuals | Contact at company |

---

## Tags

Tags are extracted from:
- `Individuals.Category` (comma-separated)
- `Firms.Firm Category`
- `Companies.Category`

All tags are normalized (trimmed, deduplicated) before insertion.

---

## Validation Rules

1. **Skip empty names**: Rows where the name field is empty are skipped
2. **Name splitting**: Split `First & Last Name` on the last space
3. **Unmatched orgs**: If `Invest Firm` doesn't match any org, store as text in notes
4. **Date parsing**: Handle both `M/D/YYYY` and `MM/DD/YYYY` formats

---

## Import Order

1. **Tags** - Extract from all Category fields first
2. **Organizations** - Firms, then Companies
3. **Persons** - With tag and org linking
4. **Organization→Person links** - Key People, Connections, Individuals
5. **Interactions** - With person matching

This order ensures foreign keys can be resolved properly.
