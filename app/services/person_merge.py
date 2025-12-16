"""
Person merge service for combining duplicate persons.

Handles merging all related data from source person to target person.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    Person,
    PersonEmail,
    PersonOrganization,
    Interaction,
    PendingContact,
    PendingContactStatus,
)
from app.models.tag import PersonTag
from app.models.person_phone import PersonPhone
from app.models.person_relationship import PersonRelationship
from app.models.person_employment import PersonEmployment
from app.models.person_education import PersonEducation
from app.models.person_address import PersonAddress
from app.models.person_website import PersonWebsite


class PersonMergeError(Exception):
    """Base exception for person merge errors."""
    pass


class PersonNotFoundError(PersonMergeError):
    """Raised when a person is not found."""
    pass


class SamePersonError(PersonMergeError):
    """Raised when trying to merge a person with themselves."""
    pass


def merge_persons(
    db: Session,
    source_id: UUID,
    target_id: UUID,
    field_selections: dict[str, UUID] | None = None,
    combine_notes: bool = False,
) -> dict[str, Any]:
    """
    Merge source person into target person.

    All related data from source will be transferred to target:
    - Email addresses (avoiding duplicates)
    - Phone numbers (avoiding duplicates)
    - Interactions
    - Tags (avoiding duplicates)
    - Organization relationships
    - PendingContact references
    - Notes (appended or selected based on field_selections)

    After merge, the source person is deleted.

    Args:
        db: Database session
        source_id: UUID of person to merge FROM (will be deleted)
        target_id: UUID of person to merge INTO (will be kept)
        field_selections: Dict mapping field names to the person UUID whose value to use
        combine_notes: If True, combine all notes instead of using field selection

    Returns:
        Dict with merge statistics:
        {
            "emails_transferred": int,
            "phones_transferred": int,
            "interactions_transferred": int,
            "tags_transferred": int,
            "organizations_transferred": int,
            "pending_contacts_updated": int,
        }

    Raises:
        PersonNotFoundError: If source or target person not found
        SamePersonError: If source_id == target_id
    """
    if source_id == target_id:
        raise SamePersonError("Cannot merge a person with themselves")

    # Get both persons
    source = db.query(Person).filter_by(id=source_id).first()
    if not source:
        raise PersonNotFoundError(f"Source person not found: {source_id}")

    target = db.query(Person).filter_by(id=target_id).first()
    if not target:
        raise PersonNotFoundError(f"Target person not found: {target_id}")

    stats = {
        "emails_transferred": 0,
        "phones_transferred": 0,
        "interactions_transferred": 0,
        "tags_transferred": 0,
        "organizations_transferred": 0,
        "pending_contacts_updated": 0,
        "source_name": source.full_name,
        "target_name": target.full_name,
    }

    # Apply field selections if provided
    if field_selections:
        _apply_field_selections(db, target, source, field_selections, combine_notes)

    # 1. Transfer emails (avoiding duplicates)
    stats["emails_transferred"] = _transfer_emails(db, source_id, target_id)

    # 2. Transfer phone numbers (avoiding duplicates)
    stats["phones_transferred"] = _transfer_phones(db, source_id, target_id)

    # 3. Transfer interactions
    stats["interactions_transferred"] = _transfer_interactions(db, source_id, target_id)

    # 4. Transfer tags (avoiding duplicates)
    stats["tags_transferred"] = _transfer_tags(db, source_id, target_id)

    # 5. Transfer organization relationships
    stats["organizations_transferred"] = _transfer_organizations(db, source_id, target_id)

    # 6. Update pending contacts
    stats["pending_contacts_updated"] = _update_pending_contacts(db, source_id, target_id)

    # 7. Transfer person relationships (both directions)
    _transfer_relationships(db, source_id, target_id)

    # 8. Transfer employment history
    _transfer_employment(db, source_id, target_id)

    # 9. Transfer education history
    _transfer_education(db, source_id, target_id)

    # 10. Transfer addresses
    _transfer_addresses(db, source_id, target_id)

    # 11. Transfer websites
    _transfer_websites(db, source_id, target_id)

    # 12. Handle notes - only if field_selections not provided (legacy behavior)
    if not field_selections:
        if source.notes and not target.notes:
            target.notes = source.notes
        elif source.notes and target.notes:
            # Append source notes to target notes using HTML formatting
            target.notes = f'{target.notes}<p><br></p><p><strong>--- Merged from {source.full_name} ---</strong></p>{source.notes}'

    # 8. Delete source person
    db.delete(source)
    db.flush()

    return stats


def _apply_field_selections(
    db: Session,
    target: Person,
    source: Person,
    field_selections: dict[str, UUID],
    combine_notes: bool = False,
) -> None:
    """
    Apply field selections to the target person.

    For each field, if the selected source person's UUID matches the source
    being merged, copy that field value to the target.
    """
    # Fields that can be selected
    selectable_fields = [
        "full_name",
        "first_name",
        "last_name",
        "title",
        "profile_picture",
        "birthday",
        "location",
        "phone",
        "linkedin",
        "twitter",
        "website",
        "crunchbase",
        "angellist",
        "investment_type",
        "amount_funded",
        "potential_intro_vc",
        "priority",
        "status",
        "contacted",
    ]

    for field_name in selectable_fields:
        if field_name in field_selections:
            selected_person_id = field_selections[field_name]
            # If the selected person is the source, copy value to target
            if selected_person_id == source.id:
                source_value = getattr(source, field_name)
                setattr(target, field_name, source_value)
            # If selected person is neither source nor target, look it up
            elif selected_person_id != target.id:
                other_person = db.query(Person).filter_by(id=selected_person_id).first()
                if other_person:
                    source_value = getattr(other_person, field_name)
                    setattr(target, field_name, source_value)

    # Handle notes separately - can combine or select
    if combine_notes:
        # Combine notes from all persons involved using HTML formatting
        # Notes are stored as HTML from Quill editor, so we need to combine them properly
        notes_parts = []
        if target.notes:
            notes_parts.append(target.notes)
        if source.notes:
            # Add a separator in HTML format
            notes_parts.append(f'<p><br></p><p><strong>--- From {source.full_name} ---</strong></p>{source.notes}')
        if notes_parts:
            target.notes = "".join(notes_parts)
    elif "notes" in field_selections:
        selected_person_id = field_selections["notes"]
        if selected_person_id == source.id:
            target.notes = source.notes
        elif selected_person_id != target.id:
            other_person = db.query(Person).filter_by(id=selected_person_id).first()
            if other_person:
                target.notes = other_person.notes


def _transfer_emails(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer emails from source to target, avoiding duplicates."""
    # Get existing target emails (lowercase)
    target_emails = {
        e.email.lower() for e in db.query(PersonEmail).filter_by(person_id=target_id).all()
    }

    # Get source emails
    source_emails = db.query(PersonEmail).filter_by(person_id=source_id).all()

    transferred = 0
    for email in source_emails:
        if email.email.lower() not in target_emails:
            # Transfer to target
            email.person_id = target_id
            # Ensure not primary (target keeps their primary)
            email.is_primary = False
            transferred += 1
        else:
            # Delete duplicate
            db.delete(email)

    return transferred


def _transfer_phones(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer phone numbers from source to target, avoiding duplicates."""
    import re

    def normalize_phone(phone: str) -> str:
        """Normalize phone number by removing non-digit characters."""
        return re.sub(r'\D', '', phone)

    # Get existing target phones (normalized)
    target_phones = {
        normalize_phone(p.phone)
        for p in db.query(PersonPhone).filter_by(person_id=target_id).all()
    }

    # Get source phones
    source_phones = db.query(PersonPhone).filter_by(person_id=source_id).all()

    transferred = 0
    for phone_record in source_phones:
        normalized = normalize_phone(phone_record.phone)
        if normalized not in target_phones:
            # Transfer to target
            phone_record.person_id = target_id
            # Ensure not primary (target keeps their primary)
            phone_record.is_primary = False
            transferred += 1
            target_phones.add(normalized)  # Prevent adding duplicates from source
        else:
            # Delete duplicate
            db.delete(phone_record)

    return transferred


def _transfer_interactions(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer all interactions from source to target."""
    result = db.query(Interaction).filter_by(person_id=source_id).update(
        {"person_id": target_id}
    )
    return result


def _transfer_tags(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer tags from source to target, avoiding duplicates."""
    # Get existing target tag IDs
    target_tag_ids = {
        pt.tag_id for pt in db.query(PersonTag).filter_by(person_id=target_id).all()
    }

    # Get source tag associations
    source_tags = db.query(PersonTag).filter_by(person_id=source_id).all()

    transferred = 0
    for pt in source_tags:
        if pt.tag_id not in target_tag_ids:
            # Create new association for target
            new_pt = PersonTag(person_id=target_id, tag_id=pt.tag_id)
            db.add(new_pt)
            transferred += 1
        # Delete source association
        db.delete(pt)

    return transferred


def _transfer_organizations(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer organization relationships, avoiding duplicates."""
    # Get existing target org relationships (org_id + relationship type)
    target_orgs = {
        (po.organization_id, po.relationship)
        for po in db.query(PersonOrganization).filter_by(person_id=target_id).all()
    }

    # Get source org relationships
    source_orgs = db.query(PersonOrganization).filter_by(person_id=source_id).all()

    transferred = 0
    for po in source_orgs:
        if (po.organization_id, po.relationship) not in target_orgs:
            # Transfer to target
            po.person_id = target_id
            transferred += 1
        else:
            # Delete duplicate
            db.delete(po)

    return transferred


def _update_pending_contacts(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Update pending contacts that reference source person."""
    result = db.query(PendingContact).filter_by(
        created_person_id=source_id
    ).update({"created_person_id": target_id})
    return result


def find_potential_duplicates(
    db: Session,
    person_id: UUID,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Find potential duplicate persons for a given person.

    Matches based on:
    - Same email addresses
    - Similar names (same last name)
    - Same domain in email

    Args:
        db: Database session
        person_id: UUID of person to find duplicates for
        limit: Maximum number of results

    Returns:
        List of potential duplicate persons with match reasons
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        return []

    # Get person's emails
    person_emails = db.query(PersonEmail).filter_by(person_id=person_id).all()
    email_addresses = {e.email.lower() for e in person_emails}

    # Add legacy email field
    if person.email:
        email_addresses.add(person.email.lower())

    # Extract domains
    domains = set()
    for email in email_addresses:
        if "@" in email:
            domain = email.split("@")[1]
            # Exclude common domains
            if domain not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
                domains.add(domain)

    potential_duplicates = []
    seen_ids = {person_id}

    # 1. Find by matching email addresses
    if email_addresses:
        matches = (
            db.query(PersonEmail)
            .filter(PersonEmail.email.in_(email_addresses))
            .filter(PersonEmail.person_id != person_id)
            .all()
        )
        for match in matches:
            if match.person_id not in seen_ids:
                seen_ids.add(match.person_id)
                p = db.query(Person).filter_by(id=match.person_id).first()
                if p:
                    potential_duplicates.append({
                        "person": p,
                        "match_reason": f"Same email: {match.email}",
                        "confidence": "high",
                    })

    # 2. Find by same last name (if we have one)
    if person.last_name and len(potential_duplicates) < limit:
        matches = (
            db.query(Person)
            .filter(Person.last_name == person.last_name)
            .filter(Person.id != person_id)
            .filter(Person.id.notin_(seen_ids))
            .limit(limit - len(potential_duplicates))
            .all()
        )
        for p in matches:
            seen_ids.add(p.id)
            potential_duplicates.append({
                "person": p,
                "match_reason": f"Same last name: {person.last_name}",
                "confidence": "medium",
            })

    # 3. Find by same email domain
    if domains and len(potential_duplicates) < limit:
        for domain in domains:
            domain_matches = (
                db.query(PersonEmail)
                .filter(PersonEmail.email.like(f"%@{domain}"))
                .filter(PersonEmail.person_id != person_id)
                .filter(PersonEmail.person_id.notin_(seen_ids))
                .limit(limit - len(potential_duplicates))
                .all()
            )
            for match in domain_matches:
                if match.person_id not in seen_ids:
                    seen_ids.add(match.person_id)
                    p = db.query(Person).filter_by(id=match.person_id).first()
                    if p:
                        potential_duplicates.append({
                            "person": p,
                            "match_reason": f"Same email domain: @{domain}",
                            "confidence": "low",
                        })
                if len(potential_duplicates) >= limit:
                    break

    return potential_duplicates[:limit]


def _transfer_relationships(db: Session, source_id: UUID, target_id: UUID) -> int:
    """
    Transfer person relationships from source to target.

    Handles both directions:
    - Relationships where source is the person_id (outgoing)
    - Relationships where source is the related_person_id (incoming)

    Avoids creating duplicates or self-referential relationships.
    """
    transferred = 0

    # Get existing target relationships (to avoid duplicates)
    target_outgoing = {
        (r.related_person_id, r.relationship_type_id)
        for r in db.query(PersonRelationship).filter_by(person_id=target_id).all()
    }
    target_incoming = {
        (r.person_id, r.relationship_type_id)
        for r in db.query(PersonRelationship).filter_by(related_person_id=target_id).all()
    }

    # Transfer outgoing relationships (source -> others)
    source_outgoing = db.query(PersonRelationship).filter_by(person_id=source_id).all()
    for rel in source_outgoing:
        # Skip if this would create a self-reference
        if rel.related_person_id == target_id:
            db.delete(rel)
            continue
        # Skip if duplicate
        if (rel.related_person_id, rel.relationship_type_id) in target_outgoing:
            db.delete(rel)
            continue
        # Transfer to target
        rel.person_id = target_id
        transferred += 1

    # Transfer incoming relationships (others -> source)
    source_incoming = db.query(PersonRelationship).filter_by(related_person_id=source_id).all()
    for rel in source_incoming:
        # Skip if this would create a self-reference
        if rel.person_id == target_id:
            db.delete(rel)
            continue
        # Skip if duplicate
        if (rel.person_id, rel.relationship_type_id) in target_incoming:
            db.delete(rel)
            continue
        # Transfer to target
        rel.related_person_id = target_id
        transferred += 1

    return transferred


def _transfer_employment(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer employment history from source to target, avoiding duplicates."""
    # Get existing target employment (org + role combination)
    target_employment = {
        (e.organization_id, e.role)
        for e in db.query(PersonEmployment).filter_by(person_id=target_id).all()
    }

    source_employment = db.query(PersonEmployment).filter_by(person_id=source_id).all()

    transferred = 0
    for emp in source_employment:
        if (emp.organization_id, emp.role) not in target_employment:
            emp.person_id = target_id
            transferred += 1
        else:
            db.delete(emp)

    return transferred


def _transfer_education(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer education history from source to target."""
    # Get existing target education
    target_education = {
        (e.institution, e.degree, e.field_of_study)
        for e in db.query(PersonEducation).filter_by(person_id=target_id).all()
    }

    source_education = db.query(PersonEducation).filter_by(person_id=source_id).all()

    transferred = 0
    for edu in source_education:
        if (edu.institution, edu.degree, edu.field_of_study) not in target_education:
            edu.person_id = target_id
            transferred += 1
        else:
            db.delete(edu)

    return transferred


def _transfer_addresses(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer addresses from source to target, avoiding duplicates."""
    # Get existing target addresses (normalize for comparison)
    target_addresses = {
        (a.street, a.city, a.country)
        for a in db.query(PersonAddress).filter_by(person_id=target_id).all()
    }

    source_addresses = db.query(PersonAddress).filter_by(person_id=source_id).all()

    transferred = 0
    for addr in source_addresses:
        if (addr.street, addr.city, addr.country) not in target_addresses:
            addr.person_id = target_id
            addr.is_primary = False  # Target keeps their primary
            transferred += 1
        else:
            db.delete(addr)

    return transferred


def _transfer_websites(db: Session, source_id: UUID, target_id: UUID) -> int:
    """Transfer websites from source to target, avoiding duplicates."""
    # Get existing target websites (normalize URLs)
    target_websites = {
        w.url.lower().rstrip('/')
        for w in db.query(PersonWebsite).filter_by(person_id=target_id).all()
    }

    source_websites = db.query(PersonWebsite).filter_by(person_id=source_id).all()

    transferred = 0
    for web in source_websites:
        normalized_url = web.url.lower().rstrip('/')
        if normalized_url not in target_websites:
            web.person_id = target_id
            web.is_primary = False  # Target keeps their primary
            transferred += 1
            target_websites.add(normalized_url)
        else:
            db.delete(web)

    return transferred
