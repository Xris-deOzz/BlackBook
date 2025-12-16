"""
Christmas Email Lists Service.

Provides business logic for managing Christmas email lists,
including suggestion generation based on location and name patterns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.person import Person
from app.models.person_address import PersonAddress
from app.models.tag import Tag


class SuggestionConfidence(str, Enum):
    """Confidence level for list suggestions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestedList(str, Enum):
    """Suggested Christmas list."""
    POLISH = "polish"
    ENGLISH = "english"


# Polish cities and keywords for detection
POLISH_KEYWORDS = [
    'poland', 'polska', 'polish',
    'warsaw', 'warszawa',
    'krakow', 'kraków', 'cracow',
    'gdansk', 'gdańsk',
    'wroclaw', 'wrocław',
    'poznan', 'poznań',
    'lodz', 'łódź',
    'katowice', 'szczecin', 'lublin', 'bydgoszcz',
    'bialystok', 'białystok', 'torun', 'toruń',
]

# Polish name suffixes
POLISH_SUFFIXES = ['ski', 'ska', 'wicz', 'icz', 'czyk', 'czak', 'owski', 'owska', 'ewski', 'ewska']

# Tag names
TAG_XMAS_POL = "Xmas POL"
TAG_XMAS_ENG = "Xmas ENG"

# Tag colors
TAG_COLOR_POL = "#DC2626"  # Red
TAG_COLOR_ENG = "#16A34A"  # Green


@dataclass
class PersonSuggestion:
    """A person with their suggested Christmas list."""
    person_id: UUID
    full_name: str
    first_name: str | None
    email: str | None
    location: str | None
    suggested_list: SuggestedList
    confidence: SuggestionConfidence
    reason: str
    tags: list  # List of Tag objects


class ChristmasService:
    """Service for managing Christmas email lists."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_christmas_tags(self) -> tuple[Tag, Tag]:
        """
        Get or create the Christmas tags.

        Returns:
            Tuple of (polish_tag, english_tag)
        """
        polish_tag = self.db.query(Tag).filter_by(name=TAG_XMAS_POL).first()
        if not polish_tag:
            polish_tag = Tag(name=TAG_XMAS_POL, color=TAG_COLOR_POL, category="People")
            self.db.add(polish_tag)

        english_tag = self.db.query(Tag).filter_by(name=TAG_XMAS_ENG).first()
        if not english_tag:
            english_tag = Tag(name=TAG_XMAS_ENG, color=TAG_COLOR_ENG, category="People")
            self.db.add(english_tag)

        self.db.commit()
        return polish_tag, english_tag

    def get_list_counts(self) -> dict[str, dict[str, int]]:
        """
        Get counts for each Christmas list.

        Returns:
            Dict with 'polish' and 'english' keys, each containing:
            - total: total people in list
            - with_email: people with email addresses
        """
        polish_tag, english_tag = self.get_or_create_christmas_tags()

        # Count Polish list
        polish_people = self.db.query(Person).filter(
            Person.tags.any(Tag.id == polish_tag.id)
        ).all()
        polish_with_email = sum(1 for p in polish_people if p.primary_email)

        # Count English list
        english_people = self.db.query(Person).filter(
            Person.tags.any(Tag.id == english_tag.id)
        ).all()
        english_with_email = sum(1 for p in english_people if p.primary_email)

        return {
            "polish": {
                "total": len(polish_people),
                "with_email": polish_with_email,
            },
            "english": {
                "total": len(english_people),
                "with_email": english_with_email,
            },
        }

    def get_list_members(self, list_type: str) -> list[dict[str, Any]]:
        """
        Get all members of a specific Christmas list.

        Args:
            list_type: 'polish' or 'english'

        Returns:
            List of person dicts with name, email, location, etc.
        """
        polish_tag, english_tag = self.get_or_create_christmas_tags()
        tag = polish_tag if list_type == "polish" else english_tag

        people = self.db.query(Person).options(
            joinedload(Person.emails),
            joinedload(Person.addresses),
            joinedload(Person.tags),
        ).filter(
            Person.tags.any(Tag.id == tag.id)
        ).order_by(Person.full_name).all()

        return [
            {
                "id": str(p.id),
                "full_name": p.full_name,
                "first_name": p.first_name,
                "email": p.primary_email,
                "location": p.location,
                "tags": [t.name for t in p.tags],
            }
            for p in people
        ]

    def _analyze_person(self, person: Person) -> tuple[SuggestedList, SuggestionConfidence, str]:
        """
        Analyze a person and suggest which list they belong to.

        Returns:
            Tuple of (suggested_list, confidence, reason)
        """
        # Check addresses for Poland
        for addr in person.addresses:
            if addr.country:
                country_lower = addr.country.lower()
                if 'poland' in country_lower or 'polska' in country_lower:
                    return SuggestedList.POLISH, SuggestionConfidence.HIGH, f"Address country: {addr.country}"
            if addr.city:
                city_lower = addr.city.lower()
                for kw in POLISH_KEYWORDS:
                    if kw in city_lower:
                        return SuggestedList.POLISH, SuggestionConfidence.HIGH, f"Address city: {addr.city}"

        # Check location field
        if person.location:
            location_lower = person.location.lower()
            for kw in POLISH_KEYWORDS:
                if kw in location_lower:
                    return SuggestedList.POLISH, SuggestionConfidence.HIGH, f"Location: {person.location}"

        # Check last name for Polish suffixes
        if person.last_name:
            last_name_lower = person.last_name.lower()
            for suffix in POLISH_SUFFIXES:
                if last_name_lower.endswith(suffix):
                    return SuggestedList.POLISH, SuggestionConfidence.MEDIUM, f"Polish surname: {person.last_name}"

        # Default to English
        return SuggestedList.ENGLISH, SuggestionConfidence.LOW, "Default (no Polish indicators)"

    def get_unassigned_suggestions(
        self,
        email_only: bool = True,
        limit: int | None = None,
    ) -> list[PersonSuggestion]:
        """
        Get people who are not assigned to any Christmas list, with suggestions.

        Args:
            email_only: Only include people with email addresses
            limit: Max number of results

        Returns:
            List of PersonSuggestion objects
        """
        polish_tag, english_tag = self.get_or_create_christmas_tags()

        # Get people not in either list
        query = self.db.query(Person).options(
            joinedload(Person.emails),
            joinedload(Person.addresses),
            joinedload(Person.tags),
        ).filter(
            ~Person.tags.any(Tag.id == polish_tag.id),
            ~Person.tags.any(Tag.id == english_tag.id),
        )

        people = query.order_by(Person.full_name).all()

        suggestions = []
        for person in people:
            email = person.primary_email

            # Skip people without email if email_only
            if email_only and not email:
                continue

            suggested_list, confidence, reason = self._analyze_person(person)

            suggestions.append(PersonSuggestion(
                person_id=person.id,
                full_name=person.full_name,
                first_name=person.first_name,
                email=email,
                location=person.location,
                suggested_list=suggested_list,
                confidence=confidence,
                reason=reason,
                tags=list(person.tags),  # Include current tags
            ))

        # Sort by confidence (high first), then by suggested list (polish first)
        confidence_order = {
            SuggestionConfidence.HIGH: 0,
            SuggestionConfidence.MEDIUM: 1,
            SuggestionConfidence.LOW: 2,
        }
        suggestions.sort(key=lambda s: (confidence_order[s.confidence], s.suggested_list.value, s.full_name))

        if limit:
            suggestions = suggestions[:limit]

        return suggestions

    def assign_to_list(self, person_id: UUID, list_type: str) -> bool:
        """
        Assign a person to a Christmas list by adding the tag.

        Args:
            person_id: The person's UUID
            list_type: 'polish' or 'english'

        Returns:
            True if successful
        """
        polish_tag, english_tag = self.get_or_create_christmas_tags()
        tag = polish_tag if list_type == "polish" else english_tag

        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            return False

        # Remove from other list if present
        other_tag = english_tag if list_type == "polish" else polish_tag
        if other_tag in person.tags:
            person.tags.remove(other_tag)

        # Add to this list
        if tag not in person.tags:
            person.tags.append(tag)

        self.db.commit()
        return True

    def remove_from_list(self, person_id: UUID, list_type: str) -> bool:
        """
        Remove a person from a Christmas list by removing the tag.

        Args:
            person_id: The person's UUID
            list_type: 'polish' or 'english'

        Returns:
            True if successful
        """
        polish_tag, english_tag = self.get_or_create_christmas_tags()
        tag = polish_tag if list_type == "polish" else english_tag

        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            return False

        if tag in person.tags:
            person.tags.remove(tag)
            self.db.commit()

        return True

    def bulk_assign_by_confidence(self, min_confidence: SuggestionConfidence) -> dict[str, int]:
        """
        Bulk assign people based on suggestions with minimum confidence.

        Args:
            min_confidence: Minimum confidence level to accept

        Returns:
            Dict with counts: {'polish': X, 'english': Y}
        """
        confidence_order = {
            SuggestionConfidence.HIGH: 0,
            SuggestionConfidence.MEDIUM: 1,
            SuggestionConfidence.LOW: 2,
        }
        min_order = confidence_order[min_confidence]

        suggestions = self.get_unassigned_suggestions(email_only=True)
        counts = {"polish": 0, "english": 0}

        for suggestion in suggestions:
            if confidence_order[suggestion.confidence] <= min_order:
                self.assign_to_list(suggestion.person_id, suggestion.suggested_list.value)
                counts[suggestion.suggested_list.value] += 1

        return counts

    def export_list_csv(self, list_type: str) -> str:
        """
        Export a Christmas list to CSV format.

        Args:
            list_type: 'polish' or 'english'

        Returns:
            CSV string content
        """
        import csv
        import io

        members = self.get_list_members(list_type)
        language = "Polish" if list_type == "polish" else "English"

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "First Name", "Email", "Location", "Tags", "Language"])

        for member in members:
            if member["email"]:  # Only include people with email
                writer.writerow([
                    member["full_name"],
                    member["first_name"] or "",
                    member["email"],
                    member["location"] or "",
                    ", ".join(member["tags"]) if member["tags"] else "",
                    language,
                ])

        return output.getvalue()


def get_christmas_service(db: Session) -> ChristmasService:
    """Get a Christmas service instance."""
    return ChristmasService(db)
