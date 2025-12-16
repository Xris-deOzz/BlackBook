"""
Duplicate detection and merge service for persons.

Handles finding duplicate persons and merging them together.
Includes fuzzy matching for similar first names (nicknames/abbreviations).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Person, PersonEmail, PersonPhone, PersonOrganization, Tag, Interaction, DuplicateExclusion


# Comprehensive nickname/abbreviation mappings
# Maps canonical (full) names to list of common nicknames/abbreviations
NICKNAME_MAP: dict[str, list[str]] = {
    # Male names
    "william": ["will", "bill", "billy", "willy", "liam"],
    "robert": ["rob", "robbie", "bob", "bobby", "bert"],
    "richard": ["rich", "rick", "ricky", "dick", "dickie"],
    "michael": ["mike", "mikey", "mick", "mickey"],
    "james": ["jim", "jimmy", "jamie", "jem"],
    "john": ["johnny", "jon", "jack"],
    "christopher": ["chris", "kit", "topher"],
    "thomas": ["tom", "tommy", "thom"],
    "charles": ["charlie", "chuck", "chas"],
    "daniel": ["dan", "danny"],
    "matthew": ["matt", "matty"],
    "anthony": ["tony", "ant"],
    "joseph": ["joe", "joey", "jo"],
    "david": ["dave", "davy"],
    "edward": ["ed", "eddie", "ted", "teddy", "ned"],
    "andrew": ["andy", "drew"],
    "nicholas": ["nick", "nicky", "nico"],
    "alexander": ["alex", "al", "alec", "xander", "sandy"],
    "jonathan": ["jon", "johnny", "nathan"],
    "benjamin": ["ben", "benny", "benji"],
    "samuel": ["sam", "sammy"],
    "gregory": ["greg", "gregg"],
    "timothy": ["tim", "timmy"],
    "stephen": ["steve", "stevie"],
    "steven": ["steve", "stevie"],
    "patrick": ["pat", "patty", "paddy"],
    "peter": ["pete", "petey"],
    "raymond": ["ray", "raymo"],
    "kenneth": ["ken", "kenny"],
    "gerald": ["gerry", "jerry"],
    "lawrence": ["larry", "laurie"],
    "phillip": ["phil"],
    "philip": ["phil"],
    "jeffrey": ["jeff"],
    "geoffrey": ["geoff", "jeff"],
    "ronald": ["ron", "ronnie"],
    "donald": ["don", "donnie"],
    "harold": ["harry", "hal"],
    "henry": ["harry", "hank"],
    "frederick": ["fred", "freddy", "freddie"],
    "eugene": ["gene"],
    "vincent": ["vince", "vinnie", "vin"],
    "leonard": ["leo", "lenny", "len"],
    "theodore": ["ted", "teddy", "theo"],
    "nathaniel": ["nate", "nathan", "nat"],
    "zachary": ["zach", "zack"],
    "jacob": ["jake", "jack"],
    "joshua": ["josh"],
    "abraham": ["abe"],
    "albert": ["al", "bert"],
    "alfred": ["al", "fred", "alfie"],
    "arnold": ["arnie"],
    "bernard": ["bernie"],
    "clifford": ["cliff"],
    "douglas": ["doug"],
    "francis": ["frank", "fran"],
    "franklin": ["frank"],
    "jerome": ["jerry"],
    "maximilian": ["max"],
    "maxwell": ["max"],
    "sebastian": ["seb", "bastian"],
    "terrence": ["terry"],
    "terence": ["terry"],
    "walter": ["walt", "wally"],
    
    # Female names
    "elizabeth": ["liz", "lizzy", "lizzie", "beth", "betty", "betsy", "eliza", "ellie", "ella"],
    "katherine": ["kate", "katie", "kathy", "kat", "kay", "kitty"],
    "catherine": ["kate", "katie", "cathy", "cat", "kay", "kitty"],
    "margaret": ["maggie", "meg", "peggy", "marge", "margie", "greta"],
    "jennifer": ["jen", "jenny", "jenn"],
    "jessica": ["jess", "jessie"],
    "christine": ["chris", "chrissy", "tina"],
    "christina": ["chris", "chrissy", "tina"],
    "patricia": ["pat", "patty", "trish", "tricia"],
    "deborah": ["deb", "debbie", "debby"],
    "rebecca": ["becca", "becky", "reba"],
    "susan": ["sue", "suzy", "susie"],
    "suzanne": ["sue", "suzy"],
    "stephanie": ["steph", "stephie"],
    "victoria": ["vicky", "vicki", "vic", "tori"],
    "virginia": ["ginny", "ginger"],
    "alexandra": ["alex", "alexa", "lexi", "sandra", "sandy"],
    "samantha": ["sam", "sammy"],
    "melissa": ["mel", "missy", "lissa"],
    "melanie": ["mel"],
    "nicole": ["nicky", "nikki", "cole"],
    "danielle": ["dani", "danni"],
    "natalie": ["nat", "nattie"],
    "jacqueline": ["jackie", "jacqui"],
    "madeleine": ["maddy", "maddie"],
    "madeline": ["maddy", "maddie"],
    "abigail": ["abby", "gail"],
    "allison": ["ally", "ali", "allie"],
    "alison": ["ally", "ali", "allie"],
    "amanda": ["mandy", "amy"],
    "angelina": ["angie", "angel"],
    "angela": ["angie", "angel"],
    "annabelle": ["anna", "belle", "annie"],
    "barbara": ["barb", "barbie"],
    "beatrice": ["bea", "trixie"],
    "caroline": ["carrie", "carol"],
    "carolyn": ["carrie", "carol"],
    "cassandra": ["cass", "cassie", "sandy"],
    "charlotte": ["charlie", "lottie"],
    "cynthia": ["cindy"],
    "dorothy": ["dot", "dotty", "dottie"],
    "eleanor": ["ellie", "ella", "nell", "nelly"],
    "emily": ["em", "emmy"],
    "evelyn": ["evie", "eve"],
    "florence": ["flo", "flossie"],
    "frances": ["fran", "frankie"],
    "gabriella": ["gabby", "gabi", "ella"],
    "genevieve": ["gen", "genny"],
    "geraldine": ["geri", "gerry"],
    "gertrude": ["gert", "gertie", "trudy"],
    "gwendolyn": ["gwen", "wendy"],
    "harriet": ["hattie"],
    "isabella": ["bella", "izzy", "izzie"],
    "josephine": ["jo", "josie"],
    "judith": ["judy", "judi"],
    "julia": ["jules", "julie"],
    "juliana": ["jules", "julie", "ana"],
    "kimberly": ["kim", "kimmy"],
    "lillian": ["lily", "lilly", "lil"],
    "lorraine": ["lori"],
    "louisa": ["lou"],
    "louise": ["lou"],
    "lucille": ["lucy", "lou"],
    "lydia": ["liddy"],
    "marilyn": ["mary"],
    "michaela": ["micki", "kayla", "miki"],
    "mildred": ["millie", "milly"],
    "miranda": ["mandy", "randi"],
    "nancy": ["nan"],
    "olivia": ["liv", "livvy"],
    "pamela": ["pam"],
    "penelope": ["penny"],
    "priscilla": ["cilla", "prissy"],
    "rachael": ["rach"],
    "rachel": ["rach"],
    "roberta": ["bobbie", "robbie"],
    "rosemary": ["rosie", "rose"],
    "sandra": ["sandy", "sandi"],
    "sarah": ["sally", "sadie"],
    "sophia": ["sophie"],
    "tabitha": ["tabby"],
    "tamara": ["tammy", "tam"],
    "theresa": ["terry", "tess", "tessa"],
    "teresa": ["terry", "tess", "tessa"],
    "valerie": ["val"],
    "veronica": ["ronnie", "roni"],
    "winifred": ["winnie"],
    "yvonne": ["eve", "evie"],
}

# Build reverse mapping (nickname -> set of all related names including canonical)
NICKNAME_REVERSE_MAP: dict[str, set[str]] = {}
for canonical, nicknames in NICKNAME_MAP.items():
    # Add canonical to its own set
    if canonical not in NICKNAME_REVERSE_MAP:
        NICKNAME_REVERSE_MAP[canonical] = {canonical}
    for nick in nicknames:
        NICKNAME_REVERSE_MAP[canonical].add(nick)
    # Add reverse mappings
    for nick in nicknames:
        if nick not in NICKNAME_REVERSE_MAP:
            NICKNAME_REVERSE_MAP[nick] = set()
        NICKNAME_REVERSE_MAP[nick].add(canonical)
        NICKNAME_REVERSE_MAP[nick].update(nicknames)


def get_name_variants(first_name: str) -> set[str]:
    """Get all possible variants of a first name (including itself)."""
    if not first_name:
        return set()
    
    name_lower = first_name.lower().strip()
    variants = {name_lower}
    
    # Check if this name is a canonical name with nicknames
    if name_lower in NICKNAME_MAP:
        variants.update(NICKNAME_MAP[name_lower])
    
    # Check if this name is a nickname that maps to canonical names
    if name_lower in NICKNAME_REVERSE_MAP:
        variants.update(NICKNAME_REVERSE_MAP[name_lower])
    
    return variants


def names_are_similar(name1: str | None, name2: str | None) -> bool:
    """Check if two first names are similar (same or nickname variants)."""
    if not name1 or not name2:
        return False
    
    name1_lower = name1.lower().strip()
    name2_lower = name2.lower().strip()
    
    # Exact match
    if name1_lower == name2_lower:
        return True
    
    # Check if they share any variants
    variants1 = get_name_variants(name1_lower)
    variants2 = get_name_variants(name2_lower)
    
    return bool(variants1 & variants2)


@dataclass
class DuplicateGroup:
    """A group of persons with the same name."""
    full_name: str
    count: int
    persons: list[Person]


@dataclass
class FuzzyDuplicateGroup:
    """A group of persons with similar names (same last name, similar first name)."""
    last_name: str
    count: int
    persons: list[Person]
    match_reason: str = ""  # e.g., "Chris ↔ Christopher"
    confidence: str = "medium"  # low, medium, high
    has_shared_email_domain: bool = False
    has_shared_organization: bool = False


@dataclass
class MergeResult:
    """Result of a merge operation."""
    kept_person_id: UUID
    merged_person_ids: list[UUID]
    emails_transferred: int
    phones_transferred: int
    orgs_transferred: int
    tags_transferred: int
    interactions_transferred: int


@dataclass
class MergeAllResult:
    """Result of merging all duplicates."""
    groups_merged: int
    total_persons_merged: int
    emails_transferred: int
    phones_transferred: int
    orgs_transferred: int
    tags_transferred: int
    interactions_transferred: int


class DuplicateService:
    """Service for detecting and merging duplicate persons."""

    def __init__(self, db: Session):
        self.db = db

    def find_duplicates(self, min_name_words: int = 2) -> list[DuplicateGroup]:
        """
        Find all persons with duplicate full names.

        Args:
            min_name_words: Minimum number of words in name to consider (default 2 to skip first-name-only)

        Returns:
            List of DuplicateGroup objects sorted by count descending
        """
        # Find names with duplicates
        duplicate_names = (
            self.db.query(Person.full_name, func.count(Person.id).label('count'))
            .filter(Person.full_name.isnot(None))
            .group_by(Person.full_name)
            .having(func.count(Person.id) > 1)
            .order_by(func.count(Person.id).desc())
            .all()
        )

        groups = []
        for name, count in duplicate_names:
            # Skip names with fewer words than required
            if name and len(name.split()) >= min_name_words:
                persons = (
                    self.db.query(Person)
                    .filter(Person.full_name == name)
                    .order_by(Person.created_at)
                    .all()
                )
                groups.append(DuplicateGroup(
                    full_name=name,
                    count=count,
                    persons=persons
                ))

        return groups

    def find_fuzzy_duplicates(self) -> list[FuzzyDuplicateGroup]:
        """
        Find persons with similar names (same last name, similar first name).
        
        Uses nickname/abbreviation matching to find potential duplicates like:
        - Chris Smith vs Christopher Smith
        - Mike Johnson vs Michael Johnson
        
        Excludes pairs that have been marked as "not duplicates".
        
        Returns:
            List of FuzzyDuplicateGroup objects sorted by confidence then count
        """
        # Get all excluded pairs for fast lookup
        excluded_pairs = self.get_excluded_pairs()
        
        # Get all persons with both first and last name
        persons = (
            self.db.query(Person)
            .filter(Person.first_name.isnot(None))
            .filter(Person.last_name.isnot(None))
            .filter(Person.first_name != "")
            .filter(Person.last_name != "")
            .all()
        )
        
        # Group by last name
        by_last_name: dict[str, list[Person]] = defaultdict(list)
        for person in persons:
            if person.last_name:
                by_last_name[person.last_name.lower().strip()].append(person)
        
        fuzzy_groups: list[FuzzyDuplicateGroup] = []
        
        # For each last name group, find persons with similar first names
        for last_name, last_name_persons in by_last_name.items():
            if len(last_name_persons) < 2:
                continue
            
            # Track which persons have been grouped
            grouped_ids: set[UUID] = set()
            
            for i, person1 in enumerate(last_name_persons):
                if person1.id in grouped_ids:
                    continue
                
                similar_persons = [person1]
                first_names_in_group = {person1.first_name}
                
                for person2 in last_name_persons[i+1:]:
                    if person2.id in grouped_ids:
                        continue
                    
                    # Check if this pair is excluded
                    if self.is_pair_excluded(person1.id, person2.id, excluded_pairs):
                        continue
                    
                    # Check if first names are similar but NOT exact same full name
                    # (exact duplicates are handled by find_duplicates)
                    if (person1.full_name != person2.full_name and 
                        names_are_similar(person1.first_name, person2.first_name)):
                        similar_persons.append(person2)
                        first_names_in_group.add(person2.first_name)
                
                # Only create group if we found similar (but not exact) matches
                if len(similar_persons) > 1:
                    # Double-check: filter out any person who is excluded from ALL others in the group
                    # This handles the case where person was added before an exclusion with another member
                    valid_persons = []
                    for p in similar_persons:
                        has_valid_match = False
                        for other in similar_persons:
                            if p.id != other.id and not self.is_pair_excluded(p.id, other.id, excluded_pairs):
                                has_valid_match = True
                                break
                        if has_valid_match:
                            valid_persons.append(p)
                    
                    if len(valid_persons) < 2:
                        continue
                    
                    similar_persons = valid_persons
                    first_names_in_group = {p.first_name for p in similar_persons}
                    
                    for p in similar_persons:
                        grouped_ids.add(p.id)
                    
                    # Determine confidence and additional signals
                    confidence = "medium"
                    has_shared_domain = self._check_shared_email_domain(similar_persons)
                    has_shared_org = self._check_shared_organization(similar_persons)
                    
                    if has_shared_domain or has_shared_org:
                        confidence = "high"
                    
                    # Build match reason string
                    sorted_names = sorted(first_names_in_group, key=lambda x: x.lower() if x else "")
                    match_reason = " ↔ ".join(sorted_names)
                    
                    # Sort persons by created_at
                    similar_persons.sort(key=lambda p: p.created_at)
                    
                    fuzzy_groups.append(FuzzyDuplicateGroup(
                        last_name=person1.last_name or last_name,
                        count=len(similar_persons),
                        persons=similar_persons,
                        match_reason=match_reason,
                        confidence=confidence,
                        has_shared_email_domain=has_shared_domain,
                        has_shared_organization=has_shared_org,
                    ))
        
        # Sort by confidence (high first), then by count
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        fuzzy_groups.sort(key=lambda g: (confidence_order.get(g.confidence, 2), -g.count))
        
        return fuzzy_groups

    def _check_shared_email_domain(self, persons: list[Person]) -> bool:
        """Check if any persons share a non-common email domain."""
        common_domains = {
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", 
            "aol.com", "icloud.com", "live.com", "msn.com", "mail.com"
        }
        
        domains: dict[str, int] = defaultdict(int)
        
        for person in persons:
            person_domains: set[str] = set()
            for email_obj in person.emails:
                if email_obj.email and "@" in email_obj.email:
                    domain = email_obj.email.split("@")[1].lower()
                    if domain not in common_domains:
                        person_domains.add(domain)
            # Count each domain once per person
            for domain in person_domains:
                domains[domain] += 1
        
        # Check if any domain appears for multiple persons
        return any(count > 1 for count in domains.values())

    def _check_shared_organization(self, persons: list[Person]) -> bool:
        """Check if any persons share an organization."""
        org_ids: dict[UUID, int] = defaultdict(int)
        
        for person in persons:
            person_orgs: set[UUID] = set()
            for po in person.organizations:
                person_orgs.add(po.organization_id)
            for org_id in person_orgs:
                org_ids[org_id] += 1
        
        return any(count > 1 for count in org_ids.values())

    def get_duplicate_group(self, full_name: str) -> DuplicateGroup | None:
        """Get a specific duplicate group by name."""
        persons = (
            self.db.query(Person)
            .filter(Person.full_name == full_name)
            .order_by(Person.created_at)
            .all()
        )

        if len(persons) < 2:
            return None

        return DuplicateGroup(
            full_name=full_name,
            count=len(persons),
            persons=persons
        )

    def get_fuzzy_duplicate_group(self, person_ids: list[UUID]) -> FuzzyDuplicateGroup | None:
        """Get a specific fuzzy duplicate group by person IDs."""
        persons = (
            self.db.query(Person)
            .filter(Person.id.in_(person_ids))
            .order_by(Person.created_at)
            .all()
        )

        if len(persons) < 2:
            return None

        first_names = {p.first_name for p in persons if p.first_name}
        match_reason = " ↔ ".join(sorted(first_names, key=lambda x: x.lower()))
        
        has_shared_domain = self._check_shared_email_domain(persons)
        has_shared_org = self._check_shared_organization(persons)
        confidence = "high" if (has_shared_domain or has_shared_org) else "medium"

        return FuzzyDuplicateGroup(
            last_name=persons[0].last_name or "",
            count=len(persons),
            persons=persons,
            match_reason=match_reason,
            confidence=confidence,
            has_shared_email_domain=has_shared_domain,
            has_shared_organization=has_shared_org,
        )

    def merge_persons(self, keep_id: UUID, merge_ids: list[UUID]) -> MergeResult:
        """
        Merge multiple persons into one.

        The person with keep_id will be kept, and data from merge_ids will be
        transferred to it. Persons in merge_ids will be deleted.

        Args:
            keep_id: ID of the person to keep
            merge_ids: IDs of persons to merge into the kept person

        Returns:
            MergeResult with statistics
        """
        keep_person = self.db.query(Person).filter_by(id=keep_id).first()
        if not keep_person:
            raise ValueError(f"Person {keep_id} not found")

        result = MergeResult(
            kept_person_id=keep_id,
            merged_person_ids=merge_ids,
            emails_transferred=0,
            phones_transferred=0,
            orgs_transferred=0,
            tags_transferred=0,
            interactions_transferred=0,
        )

        for merge_id in merge_ids:
            merge_person = self.db.query(Person).filter_by(id=merge_id).first()
            if not merge_person:
                continue

            # Transfer empty fields from merge_person to keep_person
            self._transfer_fields(keep_person, merge_person)

            # Transfer emails
            result.emails_transferred += self._transfer_emails(keep_person, merge_person)

            # Transfer phones
            result.phones_transferred += self._transfer_phones(keep_person, merge_person)

            # Transfer organization links
            result.orgs_transferred += self._transfer_organizations(keep_person, merge_person)

            # Transfer tags
            result.tags_transferred += self._transfer_tags(keep_person, merge_person)

            # Transfer interactions
            result.interactions_transferred += self._transfer_interactions(keep_person, merge_person)

            # Delete the merged person
            self.db.delete(merge_person)

        self.db.commit()
        return result

    def _transfer_fields(self, keep: Person, merge: Person) -> None:
        """Transfer non-empty fields from merge to keep where keep is empty."""
        fields = [
            'first_name', 'last_name', 'title', 'phone', 'email',
            'linkedin', 'twitter', 'website', 'crunchbase', 'angellist',
            'profile_picture', 'birthday', 'location',
            'investment_type', 'amount_funded', 'potential_intro_vc'
        ]

        for field in fields:
            keep_value = getattr(keep, field)
            merge_value = getattr(merge, field)
            if not keep_value and merge_value:
                setattr(keep, field, merge_value)

        # Merge notes
        if merge.notes:
            if keep.notes:
                keep.notes = f"{keep.notes}\n\n---\n\n{merge.notes}"
            else:
                keep.notes = merge.notes

        # Merge custom_fields
        if merge.custom_fields:
            if keep.custom_fields is None:
                keep.custom_fields = {}
            for key, value in merge.custom_fields.items():
                if key not in keep.custom_fields:
                    keep.custom_fields[key] = value

        # Mark as contacted if either was contacted
        if merge.contacted:
            keep.contacted = True

    def _transfer_emails(self, keep: Person, merge: Person) -> int:
        """Transfer emails from merge to keep. Returns count transferred."""
        existing_emails = {pe.email.lower() for pe in keep.emails}
        transferred = 0

        for person_email in merge.emails:
            if person_email.email.lower() not in existing_emails:
                person_email.person_id = keep.id
                transferred += 1
            else:
                self.db.delete(person_email)

        return transferred

    def _transfer_phones(self, keep: Person, merge: Person) -> int:
        """Transfer phones from merge to keep. Returns count transferred."""
        # Normalize phone numbers for comparison (remove spaces, dashes, parens)
        def normalize_phone(phone: str) -> str:
            return ''.join(c for c in phone if c.isdigit() or c == '+')

        existing_phones = {normalize_phone(pp.phone) for pp in keep.phones}
        transferred = 0

        for person_phone in list(merge.phones):
            if normalize_phone(person_phone.phone) not in existing_phones:
                person_phone.person_id = keep.id
                transferred += 1
                existing_phones.add(normalize_phone(person_phone.phone))
            else:
                self.db.delete(person_phone)

        return transferred

    def _transfer_organizations(self, keep: Person, merge: Person) -> int:
        """Transfer organization links from merge to keep. Returns count transferred."""
        existing_orgs = {po.organization_id for po in keep.organizations}
        transferred = 0

        for person_org in list(merge.organizations):
            if person_org.organization_id not in existing_orgs:
                person_org.person_id = keep.id
                transferred += 1
            else:
                self.db.delete(person_org)

        return transferred

    def _transfer_tags(self, keep: Person, merge: Person) -> int:
        """Transfer tags from merge to keep. Returns count transferred."""
        existing_tags = {t.id for t in keep.tags}
        transferred = 0

        for tag in list(merge.tags):
            if tag.id not in existing_tags:
                keep.tags.append(tag)
                transferred += 1
            merge.tags.remove(tag)

        return transferred

    def _transfer_interactions(self, keep: Person, merge: Person) -> int:
        """Transfer interactions from merge to keep. Returns count transferred."""
        transferred = 0

        interactions = self.db.query(Interaction).filter_by(person_id=merge.id).all()
        for interaction in interactions:
            interaction.person_id = keep.id
            transferred += 1

        return transferred

    def merge_all(self, min_name_words: int = 2) -> MergeAllResult:
        """
        Merge all duplicate groups at once.

        For each duplicate group, keeps the oldest person (earliest created_at)
        and merges all others into it.

        Args:
            min_name_words: Minimum number of words in name to consider

        Returns:
            MergeAllResult with aggregate statistics
        """
        result = MergeAllResult(
            groups_merged=0,
            total_persons_merged=0,
            emails_transferred=0,
            phones_transferred=0,
            orgs_transferred=0,
            tags_transferred=0,
            interactions_transferred=0,
        )

        # Get all duplicate groups
        duplicate_groups = self.find_duplicates(min_name_words)

        for group in duplicate_groups:
            if len(group.persons) < 2:
                continue

            # Keep the oldest person (first created)
            keep_person = group.persons[0]  # Already sorted by created_at
            merge_ids = [p.id for p in group.persons[1:]]

            # Merge this group
            merge_result = self.merge_persons(keep_person.id, merge_ids)

            # Aggregate results
            result.groups_merged += 1
            result.total_persons_merged += len(merge_ids)
            result.emails_transferred += merge_result.emails_transferred
            result.phones_transferred += merge_result.phones_transferred
            result.orgs_transferred += merge_result.orgs_transferred
            result.tags_transferred += merge_result.tags_transferred
            result.interactions_transferred += merge_result.interactions_transferred

        return result

    def count_duplicates(self, min_name_words: int = 2) -> int:
        """Count total number of duplicate groups."""
        duplicate_names = (
            self.db.query(Person.full_name)
            .filter(Person.full_name.isnot(None))
            .group_by(Person.full_name)
            .having(func.count(Person.id) > 1)
            .all()
        )

        count = 0
        for (name,) in duplicate_names:
            if name and len(name.split()) >= min_name_words:
                count += 1

        return count

    def count_fuzzy_duplicates(self) -> int:
        """Count total number of fuzzy duplicate groups."""
        return len(self.find_fuzzy_duplicates())

    # ==================== Duplicate Exclusion Methods ====================
    
    def get_excluded_pairs(self) -> set[tuple[UUID, UUID]]:
        """
        Get all excluded pairs from the database.
        Returns a set of tuples (smaller_id, larger_id) for fast lookup.
        """
        exclusions = self.db.query(DuplicateExclusion).all()
        return {(e.person1_id, e.person2_id) for e in exclusions}
    
    def is_pair_excluded(self, id1: UUID, id2: UUID, excluded_pairs: set[tuple[UUID, UUID]] | None = None) -> bool:
        """Check if a pair of persons is excluded from duplicate detection."""
        ordered = DuplicateExclusion.make_ordered_pair(id1, id2)
        
        if excluded_pairs is not None:
            return ordered in excluded_pairs
        
        # Query the database directly
        exists = self.db.query(DuplicateExclusion).filter_by(
            person1_id=ordered[0],
            person2_id=ordered[1]
        ).first()
        return exists is not None
    
    def exclude_duplicates(self, person_ids: list[UUID]) -> int:
        """
        Mark all pairs in the given list as "not duplicates".
        
        Args:
            person_ids: List of person IDs that should not be considered duplicates of each other
            
        Returns:
            Number of exclusion pairs created
        """
        if len(person_ids) < 2:
            return 0
        
        created = 0
        # Create exclusions for all pairs
        for i, id1 in enumerate(person_ids):
            for id2 in person_ids[i+1:]:
                ordered = DuplicateExclusion.make_ordered_pair(id1, id2)
                
                # Check if already exists
                existing = self.db.query(DuplicateExclusion).filter_by(
                    person1_id=ordered[0],
                    person2_id=ordered[1]
                ).first()
                
                if not existing:
                    exclusion = DuplicateExclusion(
                        person1_id=ordered[0],
                        person2_id=ordered[1]
                    )
                    self.db.add(exclusion)
                    created += 1
        
        self.db.commit()
        return created
    
    def remove_exclusion(self, id1: UUID, id2: UUID) -> bool:
        """Remove an exclusion for a pair of persons."""
        ordered = DuplicateExclusion.make_ordered_pair(id1, id2)
        exclusion = self.db.query(DuplicateExclusion).filter_by(
            person1_id=ordered[0],
            person2_id=ordered[1]
        ).first()
        
        if exclusion:
            self.db.delete(exclusion)
            self.db.commit()
            return True
        return False
    
    def get_exclusion_count(self) -> int:
        """Get total number of exclusion pairs."""
        return self.db.query(DuplicateExclusion).count()

    def get_exclusions_with_details(self) -> list[dict[str, Any]]:
        """
        Get all exclusions with person details for display.
        
        Returns:
            List of dicts with exclusion info and person names
        """
        exclusions = (
            self.db.query(DuplicateExclusion)
            .order_by(DuplicateExclusion.created_at.desc())
            .all()
        )
        
        result = []
        for exclusion in exclusions:
            person1 = self.db.query(Person).filter_by(id=exclusion.person1_id).first()
            person2 = self.db.query(Person).filter_by(id=exclusion.person2_id).first()
            
            result.append({
                "id": exclusion.id,
                "person1_id": exclusion.person1_id,
                "person2_id": exclusion.person2_id,
                "person1_name": person1.full_name if person1 else "(Deleted)",
                "person2_name": person2.full_name if person2 else "(Deleted)",
                "person1_title": person1.title if person1 else None,
                "person2_title": person2.title if person2 else None,
                "created_at": exclusion.created_at,
            })
        
        return result

    def remove_exclusion_by_id(self, exclusion_id: UUID) -> bool:
        """Remove an exclusion by its ID."""
        exclusion = self.db.query(DuplicateExclusion).filter_by(id=exclusion_id).first()
        if exclusion:
            self.db.delete(exclusion)
            self.db.commit()
            return True
        return False


def get_duplicate_service(db: Session) -> DuplicateService:
    """Get a DuplicateService instance."""
    return DuplicateService(db)
