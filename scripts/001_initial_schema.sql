-- Perun's BlackBook - Base Schema
-- Version: 2025.12.19.8
-- 
-- Creates base tables that migrations build upon.
-- Run migrations with: alembic upgrade head

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- BASE ENUM TYPES
-- ============================================

CREATE TYPE org_type AS ENUM (
    'investment_firm', 'company', 'law_firm', 'bank', 'accelerator', 'other'
);

CREATE TYPE person_status AS ENUM (
    'active', 'inactive', 'archived'
);

CREATE TYPE interaction_medium AS ENUM (
    'email', 'meeting', 'call', 'linkedin', 'lunch', 'coffee', 
    'event', 'video_call', 'text', 'other'
);

CREATE TYPE relationship_type AS ENUM (
    'affiliated_with', 'peer_history', 'key_person', 'connection', 'contact_at',
    'current_employee', 'former_employee', 'board_member', 'advisor', 'investor', 'founder'
);

-- ============================================
-- BASE TABLES (required before migrations)
-- ============================================

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    org_type org_type NOT NULL DEFAULT 'other',
    category VARCHAR(200),
    description TEXT,
    website VARCHAR(500),
    crunchbase VARCHAR(500),
    priority_rank INTEGER DEFAULT 0,
    notes TEXT,
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Persons (minimal - migrations add more columns)
CREATE TABLE persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    full_name VARCHAR(300) NOT NULL,
    title TEXT,
    status person_status DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    contacted BOOLEAN DEFAULT FALSE,
    notes TEXT,
    phone VARCHAR(100),
    email TEXT,
    linkedin TEXT,
    crunchbase TEXT,
    angellist TEXT,
    twitter TEXT,
    website TEXT,
    location TEXT,
    investment_type TEXT,
    amount_funded TEXT,
    potential_intro_vc TEXT,
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tags
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(20) DEFAULT '#6B7280',
    category VARCHAR(50),
    subcategory VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Junction tables
CREATE TABLE person_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(person_id, tag_id)
);

CREATE TABLE organization_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(organization_id, tag_id)
);

-- Person-Organization relationships (minimal for migrations)
CREATE TABLE person_organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID REFERENCES persons(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    relationship relationship_type NOT NULL DEFAULT 'affiliated_with',
    role VARCHAR(300),
    is_current BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(person_id, organization_id, relationship)
);

-- Legacy table needed by migration l1h89i0j2k34
CREATE TABLE organization_persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    person_name TEXT,
    relationship relationship_type NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Interactions (minimal - migrations add gmail fields)
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    person_name VARCHAR(300),
    medium interaction_medium NOT NULL DEFAULT 'other',
    interaction_date DATE,
    notes TEXT,
    files_sent TEXT,
    airtable_name VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Saved views (needed at startup)
CREATE TABLE saved_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    filters JSONB DEFAULT '{}',
    sort_by VARCHAR(100),
    sort_order VARCHAR(10) DEFAULT 'asc',
    columns JSONB DEFAULT '[]',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Basic indexes
CREATE INDEX idx_organizations_name ON organizations(name);
CREATE INDEX idx_persons_full_name ON persons(full_name);
CREATE INDEX idx_persons_email ON persons(email);
CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_interactions_person ON interactions(person_id);
