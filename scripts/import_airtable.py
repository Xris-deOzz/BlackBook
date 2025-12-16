#!/usr/bin/env python3
"""
Perun's BlackBook - Airtable Import Script
Version: 2025.12.06.5

Imports data from Airtable CSV exports into PostgreSQL database.

Usage:
    python import_airtable.py [--dry-run] [--verbose]

Options:
    --dry-run   Parse and validate without writing to database
    --verbose   Show detailed progress information
"""

import csv
import os
import sys
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from tqdm import tqdm

# ============================================
# CONFIGURATION
# ============================================

load_dotenv()

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'perunsblackbook'),
    'user': os.getenv('DB_USER', 'blackbook'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# File paths (relative to script location)
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / 'data'

CSV_FILES = {
    'individuals': DATA_DIR / 'Individuals-All Contacts.csv',
    'firms': DATA_DIR / 'Firms-All Funds.csv',
    'companies': DATA_DIR / 'Company-List.csv',
    'interactions': DATA_DIR / 'Interactions-All Interactions.csv',
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================
# DATA CLASSES FOR IMPORT TRACKING
# ============================================

@dataclass
class ImportStats:
    """Track import statistics"""
    processed: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    
    def add_error(self, msg: str, row: dict = None):
        self.errors.append({'message': msg, 'row': row})
        
    def add_warning(self, msg: str, row: dict = None):
        self.warnings.append({'message': msg, 'row': row})
    
    def summary(self) -> str:
        return (
            f"Processed: {self.processed}, "
            f"Imported: {self.imported}, "
            f"Skipped: {self.skipped}, "
            f"Errors: {len(self.errors)}, "
            f"Warnings: {len(self.warnings)}"
        )


@dataclass 
class ImportContext:
    """Shared context for import operations"""
    conn: any = None
    dry_run: bool = False
    verbose: bool = False
    
    # Lookup dictionaries (populated during import)
    org_name_to_id: dict = field(default_factory=dict)
    person_name_to_id: dict = field(default_factory=dict)
    tag_name_to_id: dict = field(default_factory=dict)
    
    # Statistics per table
    stats: dict = field(default_factory=lambda: {
        'tags': ImportStats(),
        'organizations': ImportStats(),
        'persons': ImportStats(),
        'person_organizations': ImportStats(),
        'organization_persons': ImportStats(),
        'interactions': ImportStats(),
    })


# ============================================
# CSV UTILITIES
# ============================================

def load_csv(filepath: Path) -> list[dict]:
    """
    Load CSV file handling BOM and encoding issues.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        List of dictionaries (one per row)
    """
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    rows = []
    
    # Try UTF-8 with BOM first, then UTF-8, then latin-1
    encodings = ['utf-8-sig', 'utf-8', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding, newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            logger.debug(f"Loaded {filepath.name} with {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue
    
    if not rows:
        raise ValueError(f"Could not decode {filepath} with any known encoding")
    
    logger.info(f"Loaded {len(rows)} rows from {filepath.name}")
    return rows


def clean_string(value: str) -> Optional[str]:
    """Clean and normalize a string value."""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def parse_comma_separated(value: str) -> list[str]:
    """
    Parse comma-separated values into a list.
    Handles values like "Entrepreneur,Investor: Angel"
    """
    if not value:
        return []
    
    items = []
    for item in value.split(','):
        cleaned = clean_string(item)
        if cleaned:
            items.append(cleaned)
    
    return items


# ============================================
# NAME SPLITTING
# ============================================

def split_name(full_name: str) -> tuple[str, str]:
    """
    Split a full name into first and last name.
    
    Strategy: Split on the last space.
    Edge cases are logged for manual review.
    
    Args:
        full_name: Combined first and last name
        
    Returns:
        Tuple of (first_name, last_name)
    """
    if not full_name:
        return ('', '')
    
    full_name = clean_string(full_name)
    if not full_name:
        return ('', '')
    
    parts = full_name.split()
    
    if len(parts) == 1:
        # Single word - treat as first name
        return (parts[0], '')
    
    if len(parts) == 2:
        # Simple case: "John Smith"
        return (parts[0], parts[1])
    
    # Multiple parts - split on last space
    # "Mary Jo Smith" -> ("Mary Jo", "Smith")
    # "Jean van der Berg" -> ("Jean van der", "Berg")
    first_name = ' '.join(parts[:-1])
    last_name = parts[-1]
    
    return (first_name, last_name)


# ============================================
# TAG EXTRACTION
# ============================================

def extract_all_tags(ctx: ImportContext) -> set[str]:
    """
    Extract all unique tags from all CSV files.
    
    Sources:
    - Individuals.Category (comma-separated)
    - Firms.Firm Category
    - Companies.Category
    """
    all_tags = set()
    
    # From Individuals
    if CSV_FILES['individuals'].exists():
        rows = load_csv(CSV_FILES['individuals'])
        for row in rows:
            category = row.get('Category', '')
            tags = parse_comma_separated(category)
            all_tags.update(tags)
    
    # From Firms (also split comma-separated)
    if CSV_FILES['firms'].exists():
        rows = load_csv(CSV_FILES['firms'])
        for row in rows:
            category = row.get('Firm Category', '')
            tags = parse_comma_separated(category)
            all_tags.update(tags)
    
    # From Companies (also split comma-separated)
    if CSV_FILES['companies'].exists():
        rows = load_csv(CSV_FILES['companies'])
        for row in rows:
            category = row.get('Category', '')
            tags = parse_comma_separated(category)
            all_tags.update(tags)
    
    logger.info(f"Extracted {len(all_tags)} unique tags")
    return all_tags


def import_tags(ctx: ImportContext) -> None:
    """Import all tags into the database."""
    stats = ctx.stats['tags']
    
    # Extract all unique tags
    all_tags = extract_all_tags(ctx)
    
    if ctx.dry_run:
        logger.info(f"[DRY RUN] Would import {len(all_tags)} tags")
        for tag in sorted(all_tags):
            logger.debug(f"  - {tag}")
        stats.processed = len(all_tags)
        stats.imported = len(all_tags)
        return
    
    # Insert tags
    cursor = ctx.conn.cursor()
    
    for tag_name in tqdm(sorted(all_tags), desc="Importing tags"):
        stats.processed += 1
        
        try:
            tag_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO tags (id, name)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (tag_id, tag_name)
            )
            result = cursor.fetchone()
            ctx.tag_name_to_id[tag_name] = result[0]
            stats.imported += 1
            
        except Exception as e:
            stats.add_error(f"Failed to import tag '{tag_name}': {e}")
            logger.error(f"Error importing tag '{tag_name}': {e}")
    
    ctx.conn.commit()
    logger.info(f"Tags: {stats.summary()}")


# ============================================
# ORGANIZATION IMPORT
# ============================================

def map_org_type(category: str, source: str) -> str:
    """
    Map Airtable category to org_type enum.
    
    Args:
        category: Original category from Airtable
        source: 'firms' or 'companies'
        
    Returns:
        org_type enum value
    """
    if source == 'firms':
        category_lower = (category or '').lower()
        if 'accelerator' in category_lower or 'incubator' in category_lower:
            return 'accelerator'
        return 'investment_firm'
    
    # For companies, default to 'company'
    return 'company'


def import_organizations(ctx: ImportContext) -> None:
    """Import organizations from Firms and Companies CSVs."""
    stats = ctx.stats['organizations']
    
    cursor = ctx.conn.cursor() if not ctx.dry_run else None
    
    # ---- Import Firms ----
    if CSV_FILES['firms'].exists():
        firms = load_csv(CSV_FILES['firms'])
        logger.info(f"Processing {len(firms)} firms...")
        
        for row in tqdm(firms, desc="Importing firms"):
            stats.processed += 1
            
            name = clean_string(row.get('Name', ''))
            if not name:
                stats.skipped += 1
                stats.add_warning("Skipping firm with empty name", row)
                continue
            
            org_type = map_org_type(row.get('Firm Category', ''), 'firms')
            category = clean_string(row.get('Firm Category', ''))
            
            # Handle priority_rank (may be text like "Good", "Excellent", etc.)
            priority_raw = row.get('Priority Rank', '')
            try:
                priority_rank = int(priority_raw) if priority_raw else 0
            except ValueError:
                # Map text values to numeric
                priority_map = {
                    'excellent': 3,
                    'good': 2,
                    'maybe': 1,
                    'ask for advice / references': 1,
                }
                priority_rank = priority_map.get(str(priority_raw).lower().strip(), 0)
            
            # Build custom_fields for extra data
            custom_fields = {}
            if clean_string(row.get('Select', '')):
                custom_fields['select'] = clean_string(row.get('Select', ''))
            if clean_string(row.get('Contacts', '')):
                custom_fields['contacts_note'] = clean_string(row.get('Contacts', ''))
            if clean_string(row.get('Contacts Note', '')):
                custom_fields['contacts_note_2'] = clean_string(row.get('Contacts Note', ''))
            
            if ctx.dry_run:
                org_id = str(uuid.uuid4())
                ctx.org_name_to_id[name.lower()] = org_id
                stats.imported += 1
                continue
            
            try:
                org_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO organizations 
                        (id, name, org_type, category, description, website, 
                         priority_rank, custom_fields)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        org_id,
                        name,
                        org_type,
                        category,
                        clean_string(row.get('Description', '')),
                        clean_string(row.get('Website', '')),
                        priority_rank,
                        psycopg2.extras.Json(custom_fields) if custom_fields else None,
                    )
                )
                result = cursor.fetchone()
                if result:
                    ctx.org_name_to_id[name.lower()] = result[0]
                    stats.imported += 1
                    
                    # Link category tags (split comma-separated)
                    category_tags = parse_comma_separated(category)
                    for tag_name in category_tags:
                        if tag_name in ctx.tag_name_to_id:
                            tag_id = ctx.tag_name_to_id[tag_name]
                            cursor.execute(
                                """
                                INSERT INTO organization_tags (id, organization_id, tag_id)
                                VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (str(uuid.uuid4()), result[0], tag_id)
                            )
                else:
                    # Already exists, look it up
                    cursor.execute(
                        "SELECT id FROM organizations WHERE name = %s",
                        (name,)
                    )
                    existing = cursor.fetchone()
                    if existing:
                        ctx.org_name_to_id[name.lower()] = existing[0]
                    stats.skipped += 1
                    
            except Exception as e:
                stats.add_error(f"Failed to import firm '{name}': {e}", row)
                logger.error(f"Error importing firm '{name}': {e}")
                if ctx.conn:
                    ctx.conn.rollback()
    
    # ---- Import Companies ----
    if CSV_FILES['companies'].exists():
        companies = load_csv(CSV_FILES['companies'])
        logger.info(f"Processing {len(companies)} companies...")
        
        for row in tqdm(companies, desc="Importing companies"):
            stats.processed += 1
            
            name = clean_string(row.get('Name', ''))
            if not name:
                stats.skipped += 1
                stats.add_warning("Skipping company with empty name", row)
                continue
            
            # Skip if already imported (might be duplicate from Firms)
            if name.lower() in ctx.org_name_to_id:
                stats.skipped += 1
                if ctx.verbose:
                    logger.debug(f"Skipping duplicate org: {name}")
                continue
            
            org_type = 'company'
            category = clean_string(row.get('Category', ''))
            
            # Build custom_fields
            custom_fields = {}
            for cf_field in ['Fundraising', 'Latest Stage', 'VC invested', 
                            'Other People Notes', 'Revenue Model', 'Peer Location', 'Docs']:
                value = clean_string(row.get(cf_field, ''))
                if value:
                    key = cf_field.lower().replace(' ', '_')
                    custom_fields[key] = value
            
            if ctx.dry_run:
                org_id = str(uuid.uuid4())
                ctx.org_name_to_id[name.lower()] = org_id
                stats.imported += 1
                continue
            
            try:
                org_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO organizations 
                        (id, name, org_type, category, description, website, 
                         crunchbase, notes, custom_fields)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        org_id,
                        name,
                        org_type,
                        category,
                        clean_string(row.get('Description', '')),
                        clean_string(row.get('Website', '')),
                        clean_string(row.get('Crunchbase', '')),
                        clean_string(row.get('Comments / Log', '')),
                        psycopg2.extras.Json(custom_fields) if custom_fields else None,
                    )
                )
                result = cursor.fetchone()
                if result:
                    ctx.org_name_to_id[name.lower()] = result[0]
                    stats.imported += 1
                    
                    # Link category tags (split comma-separated)
                    category_tags = parse_comma_separated(category)
                    for tag_name in category_tags:
                        if tag_name in ctx.tag_name_to_id:
                            tag_id = ctx.tag_name_to_id[tag_name]
                            cursor.execute(
                                """
                                INSERT INTO organization_tags (id, organization_id, tag_id)
                                VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (str(uuid.uuid4()), result[0], tag_id)
                            )
                else:
                    stats.skipped += 1
                    
            except Exception as e:
                stats.add_error(f"Failed to import company '{name}': {e}", row)
                logger.error(f"Error importing company '{name}': {e}")
                if ctx.conn:
                    ctx.conn.rollback()
    
    if not ctx.dry_run:
        ctx.conn.commit()
    
    logger.info(f"Organizations: {stats.summary()}")
    logger.info(f"Built org lookup with {len(ctx.org_name_to_id)} entries")


# ============================================
# PERSONS IMPORT
# ============================================

def find_org_by_name(ctx: ImportContext, name: str) -> Optional[str]:
    """
    Find organization ID by name (case-insensitive).
    
    Args:
        ctx: Import context with org lookup
        name: Organization name to find
        
    Returns:
        Organization UUID or None if not found
    """
    if not name:
        return None
    
    name_lower = name.strip().lower()
    return ctx.org_name_to_id.get(name_lower)


def import_persons(ctx: ImportContext) -> None:
    """Import persons from Individuals CSV."""
    stats = ctx.stats['persons']
    link_stats = ctx.stats['person_organizations']
    
    if not CSV_FILES['individuals'].exists():
        logger.warning("Individuals CSV not found, skipping persons import")
        return
    
    rows = load_csv(CSV_FILES['individuals'])
    logger.info(f"Processing {len(rows)} individuals...")
    
    cursor = ctx.conn.cursor() if not ctx.dry_run else None
    
    # Track edge cases for reporting
    name_edge_cases = []
    unmatched_orgs = []
    
    for row in tqdm(rows, desc="Importing persons"):
        stats.processed += 1
        
        # Get and validate name
        full_name = clean_string(row.get('First & Last Name', ''))
        if not full_name:
            stats.skipped += 1
            stats.add_warning("Skipping row with empty name", row)
            continue
        
        # Split name
        first_name, last_name = split_name(full_name)
        
        # Track edge cases (single name or 3+ parts)
        name_parts = full_name.split()
        if len(name_parts) == 1 or len(name_parts) > 2:
            name_edge_cases.append({
                'full_name': full_name,
                'first': first_name,
                'last': last_name,
                'parts': len(name_parts)
            })
        
        # Parse category into tags
        category = row.get('Category', '')
        tag_names = parse_comma_separated(category)
        
        # Map status
        status_raw = clean_string(row.get('Status', ''))
        status = 'active'  # default
        if status_raw:
            status_lower = status_raw.lower()
            if 'inactive' in status_lower:
                status = 'inactive'
            elif 'archived' in status_lower:
                status = 'archived'
        
        # Map priority (handle empty/non-numeric)
        priority_raw = row.get('Priority', '')
        try:
            priority = int(priority_raw) if priority_raw else 0
        except ValueError:
            priority = 0
        
        # Map contacted boolean
        contacted_raw = clean_string(row.get('Contacted?', ''))
        contacted = contacted_raw.lower() in ('yes', 'true', '1', 'checked') if contacted_raw else False
        
        # Build custom_fields for unmapped data
        custom_fields = {}
        # Fields we're not mapping to dedicated columns go here
        # (Most fields have dedicated columns now)
        
        if ctx.dry_run:
            person_id = str(uuid.uuid4())
            ctx.person_name_to_id[full_name.lower()] = person_id
            stats.imported += 1
            
            # Track org matching in dry run (with comma splitting)
            invest_firm = clean_string(row.get('Invest Firm', ''))
            if invest_firm:
                for org_name in parse_comma_separated(invest_firm):
                    if not find_org_by_name(ctx, org_name):
                        unmatched_orgs.append({'person': full_name, 'org': org_name, 'field': 'Invest Firm'})
            
            for peer_field in ['Peers', 'Peers 2']:
                peer_value = clean_string(row.get(peer_field, ''))
                if peer_value:
                    for org_name in parse_comma_separated(peer_value):
                        if not find_org_by_name(ctx, org_name):
                            unmatched_orgs.append({'person': full_name, 'org': org_name, 'field': peer_field})
            
            continue
        
        try:
            person_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO persons 
                    (id, first_name, last_name, full_name, title, status, priority,
                     contacted, notes, phone, email, linkedin, crunchbase, angellist,
                     twitter, website, location, investment_type, amount_funded,
                     potential_intro_vc, custom_fields)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    person_id,
                    first_name,
                    last_name,
                    full_name,
                    clean_string(row.get('Title', '')),
                    status,
                    priority,
                    contacted,
                    clean_string(row.get('Notes', '')),
                    clean_string(row.get('Tel', '')),
                    clean_string(row.get('Email', '')),
                    clean_string(row.get('LinkedIn', '')),
                    clean_string(row.get('Crunchbase', '')),
                    clean_string(row.get('Angel List', '')),
                    clean_string(row.get('Twitter', '')),
                    clean_string(row.get('Blog / Site', '')),
                    clean_string(row.get('Lives-Works Locations', '')),
                    clean_string(row.get('Investment Type', '')),
                    clean_string(row.get('Amount Funded', '')),
                    clean_string(row.get('Potential Intro - VC', '')),
                    psycopg2.extras.Json(custom_fields) if custom_fields else None,
                )
            )
            result = cursor.fetchone()
            
            if result:
                ctx.person_name_to_id[full_name.lower()] = result[0]
                stats.imported += 1
                
                # Link tags
                for tag_name in tag_names:
                    if tag_name in ctx.tag_name_to_id:
                        tag_id = ctx.tag_name_to_id[tag_name]
                        cursor.execute(
                            """
                            INSERT INTO person_tags (id, person_id, tag_id)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (str(uuid.uuid4()), result[0], tag_id)
                        )
                
                # Link to Invest Firm (affiliated_with) - may be comma-separated
                invest_firm = clean_string(row.get('Invest Firm', ''))
                if invest_firm:
                    org_names = parse_comma_separated(invest_firm)
                    for org_name in org_names:
                        org_id = find_org_by_name(ctx, org_name)
                        if org_id:
                            cursor.execute(
                                """
                                INSERT INTO person_organizations 
                                    (id, person_id, organization_id, relationship, is_current)
                                VALUES (%s, %s, %s, 'affiliated_with', TRUE)
                                ON CONFLICT DO NOTHING
                                """,
                                (str(uuid.uuid4()), result[0], org_id)
                            )
                            link_stats.imported += 1
                        else:
                            unmatched_orgs.append({'person': full_name, 'org': org_name, 'field': 'Invest Firm'})
                
                # Link to Peers and Peers 2 (peer_history) - may be comma-separated
                for peer_field in ['Peers', 'Peers 2']:
                    peer_value = clean_string(row.get(peer_field, ''))
                    if peer_value:
                        org_names = parse_comma_separated(peer_value)
                        for org_name in org_names:
                            org_id = find_org_by_name(ctx, org_name)
                            if org_id:
                                cursor.execute(
                                    """
                                    INSERT INTO person_organizations 
                                        (id, person_id, organization_id, relationship, is_current)
                                    VALUES (%s, %s, %s, 'peer_history', FALSE)
                                    ON CONFLICT DO NOTHING
                                    """,
                                    (str(uuid.uuid4()), result[0], org_id)
                                )
                                link_stats.imported += 1
                            else:
                                unmatched_orgs.append({'person': full_name, 'org': org_name, 'field': peer_field})
            else:
                stats.skipped += 1
                
        except Exception as e:
            stats.add_error(f"Failed to import person '{full_name}': {e}", row)
            logger.error(f"Error importing person '{full_name}': {e}")
            # Rollback the failed transaction and continue
            if ctx.conn:
                ctx.conn.rollback()
    
    if not ctx.dry_run:
        ctx.conn.commit()
    
    logger.info(f"Persons: {stats.summary()}")
    logger.info(f"Person-Org links: {link_stats.imported} created")
    logger.info(f"Built person lookup with {len(ctx.person_name_to_id)} entries")
    
    # Report edge cases
    if name_edge_cases:
        logger.info(f"\nName edge cases ({len(name_edge_cases)} found):")
        for case in name_edge_cases[:15]:
            logger.info(f"  '{case['full_name']}' -> first='{case['first']}', last='{case['last']}'")
        if len(name_edge_cases) > 15:
            logger.info(f"  ... and {len(name_edge_cases) - 15} more")
    
    if unmatched_orgs:
        logger.warning(f"\nUnmatched organizations ({len(unmatched_orgs)} found):")
        for um in unmatched_orgs[:15]:
            logger.warning(f"  Person '{um['person']}' -> {um['field']}: '{um['org']}'")
        if len(unmatched_orgs) > 15:
            logger.warning(f"  ... and {len(unmatched_orgs) - 15} more")


# ============================================
# ORGANIZATION -> PERSON LINKS
# ============================================

def find_person_by_name(ctx: ImportContext, name: str) -> Optional[str]:
    """
    Find person ID by name (case-insensitive).
    
    Args:
        ctx: Import context with person lookup
        name: Person name to find
        
    Returns:
        Person UUID or None if not found
    """
    if not name:
        return None
    
    name_lower = name.strip().lower()
    return ctx.person_name_to_id.get(name_lower)


def import_organization_persons(ctx: ImportContext) -> None:
    """
    Import organization->person links from Companies CSV.
    
    Fields processed:
    - Key People -> relationship='key_person'
    - Connections -> relationship='connection'
    - Individuals -> relationship='contact_at'
    """
    stats = ctx.stats['organization_persons']
    
    if not CSV_FILES['companies'].exists():
        logger.warning("Companies CSV not found, skipping org->person links")
        return
    
    rows = load_csv(CSV_FILES['companies'])
    logger.info(f"Processing org->person links from {len(rows)} companies...")
    
    cursor = ctx.conn.cursor() if not ctx.dry_run else None
    
    # Track unmatched persons
    unmatched_persons = []
    
    # Field mapping: CSV field -> relationship type
    field_mapping = {
        'Key People': 'key_person',
        'Connections': 'connection',
        'Individuals': 'contact_at',
    }
    
    for row in tqdm(rows, desc="Linking org->persons"):
        org_name = clean_string(row.get('Name', ''))
        if not org_name:
            continue
        
        org_id = find_org_by_name(ctx, org_name)
        if not org_id:
            # Org not in DB (shouldn't happen, but be safe)
            continue
        
        for field_name, relationship in field_mapping.items():
            field_value = clean_string(row.get(field_name, ''))
            if not field_value:
                continue
            
            # Split on commas to handle multiple people
            person_names = parse_comma_separated(field_value)
            
            for person_name in person_names:
                stats.processed += 1
                
                person_id = find_person_by_name(ctx, person_name)
                
                if ctx.dry_run:
                    if person_id:
                        stats.imported += 1
                    else:
                        unmatched_persons.append({
                            'org': org_name, 
                            'person': person_name, 
                            'field': field_name
                        })
                    continue
                
                try:
                    cursor.execute(
                        """
                        INSERT INTO organization_persons 
                            (id, organization_id, person_id, person_name, relationship)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            str(uuid.uuid4()),
                            org_id,
                            person_id,  # May be None
                            person_name,  # Always store name
                            relationship,
                        )
                    )
                    stats.imported += 1
                    
                    if not person_id:
                        unmatched_persons.append({
                            'org': org_name, 
                            'person': person_name, 
                            'field': field_name
                        })
                        
                except Exception as e:
                    stats.add_error(f"Failed to link {org_name} -> {person_name}: {e}", row)
                    if ctx.conn:
                        ctx.conn.rollback()
    
    if not ctx.dry_run:
        ctx.conn.commit()
    
    logger.info(f"Org->Person links: {stats.summary()}")
    
    if unmatched_persons:
        logger.info(f"\nPersons not in contacts ({len(unmatched_persons)} references):")
        for um in unmatched_persons[:15]:
            logger.info(f"  '{um['org']}' -> {um['field']}: '{um['person']}'")
        if len(unmatched_persons) > 15:
            logger.info(f"  ... and {len(unmatched_persons) - 15} more")


# ============================================
# INTERACTIONS IMPORT
# ============================================

def parse_date(date_str: str) -> Optional[str]:
    """
    Parse date from Airtable format to ISO format.
    
    Handles:
    - M/D/YYYY (e.g., "4/3/2019")
    - MM/DD/YYYY (e.g., "10/25/2017")
    
    Returns:
        ISO date string (YYYY-MM-DD) or None
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try M/D/YYYY format
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            month, day, year = parts
            return f"{year}-{int(month):02d}-{int(day):02d}"
    except (ValueError, IndexError):
        pass
    
    return None


def map_interaction_medium(medium: str) -> str:
    """
    Map Airtable interaction medium to database enum.
    """
    if not medium:
        return 'other'
    
    medium_lower = medium.lower().strip()
    
    mapping = {
        'meeting': 'meeting',
        'email': 'email',
        'linkedin': 'linkedin',
        'lunch': 'lunch',
        'call': 'call',
        'phone': 'call',
        'coffee': 'coffee',
        'video': 'video_call',
        'zoom': 'video_call',
        'text': 'text',
        'event': 'event',
        'conference': 'event',
    }
    
    for key, value in mapping.items():
        if key in medium_lower:
            return value
    
    return 'other'


def import_interactions(ctx: ImportContext) -> None:
    """Import interactions from Interactions CSV."""
    stats = ctx.stats['interactions']
    
    if not CSV_FILES['interactions'].exists():
        logger.warning("Interactions CSV not found, skipping")
        return
    
    rows = load_csv(CSV_FILES['interactions'])
    logger.info(f"Processing {len(rows)} interactions...")
    
    cursor = ctx.conn.cursor() if not ctx.dry_run else None
    
    unmatched_persons = []
    
    for row in tqdm(rows, desc="Importing interactions"):
        stats.processed += 1
        
        # Get person name from "Indiv Partner" field
        person_name = clean_string(row.get('Indiv Partner', ''))
        if not person_name:
            stats.skipped += 1
            stats.add_warning("Skipping interaction with empty person", row)
            continue
        
        # Find person
        person_id = find_person_by_name(ctx, person_name)
        
        # Parse date
        date_str = clean_string(row.get('Date of Interaction', ''))
        interaction_date = parse_date(date_str)
        
        # Map medium
        medium_raw = clean_string(row.get('Interaction Medium', ''))
        medium = map_interaction_medium(medium_raw)
        
        if ctx.dry_run:
            if person_id:
                stats.imported += 1
            else:
                unmatched_persons.append(person_name)
                stats.imported += 1  # Still count as imported (stores name)
            continue
        
        try:
            cursor.execute(
                """
                INSERT INTO interactions 
                    (id, person_id, person_name, medium, interaction_date, 
                     notes, files_sent, airtable_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    str(uuid.uuid4()),
                    person_id,  # May be None
                    person_name,  # Always store name
                    medium,
                    interaction_date,
                    clean_string(row.get('Notes', '')),
                    clean_string(row.get('Files Sent', '')),
                    clean_string(row.get('Name', '')),  # Original Airtable name
                )
            )
            stats.imported += 1
            
            if not person_id:
                unmatched_persons.append(person_name)
                
        except Exception as e:
            stats.add_error(f"Failed to import interaction for '{person_name}': {e}", row)
            logger.error(f"Error importing interaction: {e}")
            if ctx.conn:
                ctx.conn.rollback()
    
    if not ctx.dry_run:
        ctx.conn.commit()
    
    logger.info(f"Interactions: {stats.summary()}")
    
    if unmatched_persons:
        unique_unmatched = list(set(unmatched_persons))
        logger.info(f"\nInteraction persons not in contacts ({len(unique_unmatched)} unique):")
        for name in unique_unmatched[:15]:
            logger.info(f"  '{name}'")
        if len(unique_unmatched) > 15:
            logger.info(f"  ... and {len(unique_unmatched) - 15} more")


# ============================================
# DATABASE CONNECTION
# ============================================

def get_db_connection():
    """Create database connection."""
    # Check for DATABASE_URL first
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url)
    
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# MAIN IMPORT WORKFLOW
# ============================================

def run_import(dry_run: bool = False, verbose: bool = False) -> ImportContext:
    """
    Run the full import process.
    
    Args:
        dry_run: If True, parse and validate without database writes
        verbose: If True, show detailed progress
        
    Returns:
        ImportContext with statistics and lookup tables
    """
    ctx = ImportContext(dry_run=dry_run, verbose=verbose)
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Perun's BlackBook - Airtable Import")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    # Verify CSV files exist
    for name, path in CSV_FILES.items():
        if path.exists():
            logger.info(f"✓ Found {name}: {path.name}")
        else:
            logger.warning(f"✗ Missing {name}: {path}")
    
    # Connect to database (unless dry run)
    if not dry_run:
        try:
            ctx.conn = get_db_connection()
            logger.info("✓ Connected to database")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise
    
    try:
        # Step 2a: Import tags
        logger.info("\n--- Importing Tags ---")
        import_tags(ctx)
        
        # Step 2b: Import organizations
        logger.info("\n--- Importing Organizations ---")
        import_organizations(ctx)
        
        # Step 3: Import persons with linking
        logger.info("\n--- Importing Persons ---")
        import_persons(ctx)
        
        # Step 4a: Import organization->person links
        logger.info("\n--- Importing Org->Person Links ---")
        import_organization_persons(ctx)
        
        # Step 4b: Import interactions
        logger.info("\n--- Importing Interactions ---")
        import_interactions(ctx)
        
    finally:
        if ctx.conn:
            ctx.conn.close()
            logger.info("Database connection closed")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("=" * 60)
    for table, stats in ctx.stats.items():
        if stats.processed > 0:
            logger.info(f"{table}: {stats.summary()}")
    
    # Print errors and warnings
    all_errors = []
    all_warnings = []
    for table, stats in ctx.stats.items():
        all_errors.extend(stats.errors)
        all_warnings.extend(stats.warnings)
    
    if all_warnings:
        logger.info(f"\nWarnings ({len(all_warnings)}):")
        for w in all_warnings[:10]:  # Show first 10
            logger.warning(f"  - {w['message']}")
        if len(all_warnings) > 10:
            logger.warning(f"  ... and {len(all_warnings) - 10} more")
    
    if all_errors:
        logger.error(f"\nErrors ({len(all_errors)}):")
        for e in all_errors[:10]:
            logger.error(f"  - {e['message']}")
        if len(all_errors) > 10:
            logger.error(f"  ... and {len(all_errors) - 10} more")
    
    return ctx


# ============================================
# CLI ENTRY POINT
# ============================================

def main():
    """Command-line entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import Airtable data into Perun's BlackBook"
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Parse and validate without writing to database'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true', 
        help='Show detailed progress'
    )
    
    args = parser.parse_args()
    
    try:
        ctx = run_import(dry_run=args.dry_run, verbose=args.verbose)
        
        # Exit with error code if there were errors
        total_errors = sum(len(s.errors) for s in ctx.stats.values())
        sys.exit(1 if total_errors > 0 else 0)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Import failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
