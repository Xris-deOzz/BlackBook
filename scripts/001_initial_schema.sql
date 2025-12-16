-- Perun's BlackBook - Initial Database Schema
-- Version: 2025.12.06.1
-- 
-- Run this script to create all tables for the CRM
-- Usage: psql -U blackbook -d perunsblackbook -f 001_initial_schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- ENUM TYPES
-- ============================================

CREATE TYPE org_type AS ENUM (
    'investment_firm',
    'company',
    'law_firm',
    'bank',
    'accelerator',
    'other'
);

CREATE TYPE person_status AS ENUM (
    'active',
    'inactive',
    'archived'
);

CREATE TYPE interaction_medium AS ENUM (
    'email',
    'meeting',
    'call',
    'linkedin',
    'lunch',
    'coffee',
    'event',
    'video_call',
    'text',
    'other'
);

CREATE TYPE relationship_type AS ENUM (
    'affiliated_with',      -- Person works at / is affiliated with org
    'peer_history',         -- Person has past connection to org (Peers field)
    'key_person',           -- Person is a key person at org (from Company.Key People)
    'connection',           -- Person is a connection at org (from Company.Connections)
    'contact_at'            -- Person is a contact at org (from Company.Individuals)
);

-- ============================================
-- CORE TABLES
-- ============================================

-- Organizations (merged Firms + Companies)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    org_type org_type NOT NULL DEFAULT 'other',
    category VARCHAR(200),           -- Original category from Airtable
    description TEXT,
    website VARCHAR(500),
    crunchbase VARCHAR(500),
    priority_rank INTEGER DEFAULT 0,
    notes TEXT,
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_organizations_name ON organizations(name);
CREATE INDEX idx_organizations_org_type ON organizations(org_type);
CREATE INDEX idx_organizations_custom_fields ON organizations USING GIN(custom_fields);

-- Persons (from Individuals)
CREATE TABLE persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    full_name VARCHAR(300) NOT NULL,  -- Original unsplit name for reference
    title TEXT,
    status person_status DEFAULT 'active',
    priority INTEGER DEFAULT 0,       -- 0=normal, 1=important, 2=VIP
    contacted BOOLEAN DEFAULT FALSE,
    notes TEXT,
    
    -- Contact info (use TEXT for URLs that can be very long)
    phone VARCHAR(100),
    email TEXT,
    linkedin TEXT,
    crunchbase TEXT,
    angellist TEXT,
    twitter TEXT,
    website TEXT,
    
    -- Other fields
    location TEXT,
    investment_type TEXT,
    amount_funded TEXT,
    potential_intro_vc TEXT,
    
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_persons_full_name ON persons(full_name);
CREATE INDEX idx_persons_last_name ON persons(last_name);
CREATE INDEX idx_persons_email ON persons(email);
CREATE INDEX idx_persons_status ON persons(status);
CREATE INDEX idx_persons_custom_fields ON persons USING GIN(custom_fields);

-- Full-text search index on persons
CREATE INDEX idx_persons_fts ON persons USING GIN(
    to_tsvector('english', 
        COALESCE(full_name, '') || ' ' || 
        COALESCE(title, '') || ' ' || 
        COALESCE(notes, '') || ' ' ||
        COALESCE(email, '')
    )
);

-- Tags
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(20) DEFAULT '#6B7280',  -- Default gray
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tags_name ON tags(name);

-- ============================================
-- JUNCTION TABLES
-- ============================================

-- Person <-> Tag (many-to-many)
CREATE TABLE person_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(person_id, tag_id)
);

CREATE INDEX idx_person_tags_person ON person_tags(person_id);
CREATE INDEX idx_person_tags_tag ON person_tags(tag_id);

-- Organization <-> Tag (many-to-many)
CREATE TABLE organization_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(organization_id, tag_id)
);

CREATE INDEX idx_org_tags_org ON organization_tags(organization_id);
CREATE INDEX idx_org_tags_tag ON organization_tags(tag_id);

-- Person -> Organization relationships (person is linked TO org)
-- Used for: Invest Firm, Peers, Peers 2
CREATE TABLE person_organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    relationship relationship_type NOT NULL DEFAULT 'affiliated_with',
    role VARCHAR(300),                -- Job title at this org
    is_current BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(person_id, organization_id, relationship)
);

CREATE INDEX idx_person_orgs_person ON person_organizations(person_id);
CREATE INDEX idx_person_orgs_org ON person_organizations(organization_id);
CREATE INDEX idx_person_orgs_relationship ON person_organizations(relationship);

-- Organization -> Person relationships (org references a person)
-- Used for: Key People, Connections, Individuals from Companies table
CREATE TABLE organization_persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,  -- Nullable if person not in DB
    person_name TEXT,                 -- Store name even if not linked (can be long)
    relationship relationship_type NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_org_persons_org ON organization_persons(organization_id);
CREATE INDEX idx_org_persons_person ON organization_persons(person_id);
CREATE INDEX idx_org_persons_relationship ON organization_persons(relationship);

-- ============================================
-- INTERACTIONS
-- ============================================

CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    person_name VARCHAR(300),         -- Store name even if not linked
    medium interaction_medium NOT NULL DEFAULT 'other',
    interaction_date DATE,
    notes TEXT,
    files_sent TEXT,
    airtable_name VARCHAR(500),       -- Original Airtable record name
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_interactions_person ON interactions(person_id);
CREATE INDEX idx_interactions_date ON interactions(interaction_date);
CREATE INDEX idx_interactions_medium ON interactions(medium);

-- ============================================
-- SAVED VIEWS (for Airtable-like filtering)
-- ============================================

CREATE TABLE saved_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    entity_type VARCHAR(20) NOT NULL,  -- 'person' or 'organization'
    filters JSONB DEFAULT '{}',
    sort_by VARCHAR(100),
    sort_order VARCHAR(10) DEFAULT 'asc',
    columns JSONB DEFAULT '[]',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- IMPORT TRACKING
-- ============================================

-- Track import runs for debugging/auditing
CREATE TABLE import_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    import_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_file VARCHAR(200),
    records_processed INTEGER DEFAULT 0,
    records_imported INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ============================================
-- TRIGGERS FOR updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_persons_updated_at
    BEFORE UPDATE ON persons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_interactions_updated_at
    BEFORE UPDATE ON interactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_saved_views_updated_at
    BEFORE UPDATE ON saved_views
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE organizations IS 'Merged Firms and Companies from Airtable';
COMMENT ON TABLE persons IS 'Contacts from Airtable Individuals table';
COMMENT ON TABLE person_organizations IS 'Person-to-Org links (Invest Firm, Peers)';
COMMENT ON TABLE organization_persons IS 'Org-to-Person links (Key People, Connections)';
COMMENT ON COLUMN persons.full_name IS 'Original unsplit name from Airtable';
COMMENT ON COLUMN organization_persons.person_name IS 'Stored name when person not in DB';
