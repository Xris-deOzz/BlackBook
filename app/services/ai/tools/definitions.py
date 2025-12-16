"""
Tool definitions for AI Research Assistant.

Defines the available tools that AI can use for research and CRM operations.
"""

from sqlalchemy.orm import Session

from app.services.ai.tools.base import (
    Tool,
    ToolParameter,
    ToolResult,
    ToolRegistry,
)


# Tool handler implementations
import logging
_tool_logger = logging.getLogger(__name__)


async def handle_web_search(
    query: str,
    max_results: int = 5,
    include_news: bool = False,
    db: Session | None = None,
) -> ToolResult:
    """Handle web search tool invocation."""
    _tool_logger.info(f"handle_web_search called: query={query}, max_results={max_results}, db={db is not None}")

    if db is None:
        _tool_logger.error("Web search: db is None")
        return ToolResult.create_error("Database session required for search")

    try:
        from app.services.ai.search import SearchService, SearchConfig

        service = SearchService(db)

        # Check if Brave API key is available
        available = service.get_available_sources()
        _tool_logger.info(f"Available search sources: {available}")

        if "brave" not in available:
            _tool_logger.error("Brave not in available sources - API key may be missing or invalid")
            return ToolResult.create_error("Brave Search API key not configured or invalid. Please add a valid Brave API key in Settings > AI Providers.")

        config = SearchConfig(
            query=query,
            sources=["brave"],
            max_results_per_source=max_results,
            include_news=include_news,
        )
        results = await service.search(config)

        _tool_logger.info(f"Web search results: {results.total_results} results, sources_searched={results.sources_searched}, sources_failed={results.sources_failed}")

        if results.sources_failed:
            error_msg = results.sources_failed.get("brave", "Unknown error")
            _tool_logger.error(f"Brave search failed: {error_msg}")
            return ToolResult.create_error(f"Web search failed: {error_msg}")

        if not results.results:
            return ToolResult.success(
                {"results": [], "message": "No results found"},
                query=query,
            )

        return ToolResult.success(
            {
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "published_date": (
                            r.published_date.isoformat()
                            if r.published_date
                            else None
                        ),
                    }
                    for r in results.results
                ],
                "total": results.total_results,
            },
            query=query,
            sources=results.sources_searched,
        )
    except Exception as e:
        _tool_logger.exception(f"Web search exception: {str(e)}")
        return ToolResult.create_error(f"Search failed: {str(e)}")


async def handle_youtube_search(
    query: str,
    max_results: int = 5,
    db: Session | None = None,
) -> ToolResult:
    """Handle YouTube search tool invocation."""
    _tool_logger.info(f"handle_youtube_search called: query={query}, max_results={max_results}, db={db is not None}")

    if db is None:
        _tool_logger.error("YouTube search: db is None")
        return ToolResult.create_error("Database session required for search")

    try:
        from app.services.ai.search import SearchService, SearchConfig

        service = SearchService(db)

        # Check if YouTube API key is available
        available = service.get_available_sources()
        _tool_logger.info(f"Available search sources: {available}")

        if "youtube" not in available:
            _tool_logger.error("YouTube not in available sources - API key may be missing or invalid")
            return ToolResult.create_error("YouTube API key not configured or invalid. Please add a valid YouTube API key in Settings > AI Providers.")

        config = SearchConfig(
            query=query,
            sources=["youtube"],
            max_results_per_source=max_results,
        )
        results = await service.search(config)

        _tool_logger.info(f"YouTube search results: {results.total_results} results, sources_searched={results.sources_searched}, sources_failed={results.sources_failed}")

        if results.sources_failed:
            error_msg = results.sources_failed.get("youtube", "Unknown error")
            _tool_logger.error(f"YouTube search failed: {error_msg}")
            return ToolResult.create_error(f"YouTube search failed: {error_msg}")

        if not results.results:
            return ToolResult.success(
                {"results": [], "message": "No videos found"},
                query=query,
            )

        return ToolResult.success(
            {
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "channel": r.metadata.get("channel_title"),
                        "published_date": (
                            r.published_date.isoformat()
                            if r.published_date
                            else None
                        ),
                    }
                    for r in results.results
                ],
                "total": results.total_results,
            },
            query=query,
        )
    except Exception as e:
        _tool_logger.exception(f"YouTube search exception: {str(e)}")
        return ToolResult.create_error(f"YouTube search failed: {str(e)}")


async def handle_podcast_search(
    query: str,
    max_results: int = 5,
    db: Session | None = None,
) -> ToolResult:
    """Handle podcast search tool invocation."""
    if db is None:
        return ToolResult.create_error("Database session required for search")

    try:
        from app.services.ai.search import SearchService, SearchConfig

        service = SearchService(db)
        config = SearchConfig(
            query=query,
            sources=["listen_notes"],
            max_results_per_source=max_results,
        )
        results = await service.search(config)

        if not results.results:
            return ToolResult.success(
                {"results": [], "message": "No podcasts found"},
                query=query,
            )

        return ToolResult.success(
            {
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "podcast": r.metadata.get("podcast_title"),
                        "duration_minutes": r.metadata.get("duration_minutes"),
                        "published_date": (
                            r.published_date.isoformat()
                            if r.published_date
                            else None
                        ),
                    }
                    for r in results.results
                ],
                "total": results.total_results,
            },
            query=query,
        )
    except Exception as e:
        return ToolResult.create_error(f"Podcast search failed: {str(e)}")


async def handle_lookup_person(
    person_id: str | None = None,
    name: str | None = None,
    db: Session | None = None,
) -> ToolResult:
    """Handle person lookup tool invocation."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Person
        from uuid import UUID

        person = None

        if person_id:
            try:
                pid = UUID(person_id)
                person = db.query(Person).filter(Person.id == pid).first()
            except ValueError:
                return ToolResult.create_error(f"Invalid person ID: {person_id}")
        elif name:
            person = (
                db.query(Person)
                .filter(Person.full_name.ilike(f"%{name}%"))
                .first()
            )

        if not person:
            return ToolResult.success(
                {"found": False, "message": "Person not found"},
            )

        # Get primary organization if any
        org_name = None
        if person.organizations:
            org_name = person.organizations[0].organization.name

        return ToolResult.success(
            {
                "found": True,
                "person": {
                    "id": str(person.id),
                    "full_name": person.full_name,
                    "title": person.title,
                    "company": org_name,
                    "linkedin_url": person.linkedin,
                    "location": person.location,
                    "notes": person.notes[:500] if person.notes else None,
                    "tags": [t.name for t in person.tags] if person.tags else [],
                },
            },
        )
    except Exception as e:
        return ToolResult.create_error(f"Person lookup failed: {str(e)}")


async def handle_lookup_organization(
    org_id: str | None = None,
    name: str | None = None,
    db: Session | None = None,
) -> ToolResult:
    """Handle organization lookup tool invocation."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Organization
        from uuid import UUID

        org = None

        if org_id:
            try:
                oid = UUID(org_id)
                org = db.query(Organization).filter(Organization.id == oid).first()
            except ValueError:
                return ToolResult.create_error(f"Invalid organization ID: {org_id}")
        elif name:
            org = (
                db.query(Organization)
                .filter(Organization.name.ilike(f"%{name}%"))
                .first()
            )

        if not org:
            return ToolResult.success(
                {"found": False, "message": "Organization not found"},
            )

        return ToolResult.success(
            {
                "found": True,
                "organization": {
                    "id": str(org.id),
                    "name": org.name,
                    "category": org.category,
                    "org_type": org.org_type.value if org.org_type else None,
                    "website": org.website,
                    "description": org.description[:500] if org.description else None,
                },
            },
        )
    except Exception as e:
        return ToolResult.create_error(f"Organization lookup failed: {str(e)}")


async def handle_search_crm(
    query: str,
    entity_type: str = "all",
    limit: int = 10,
    db: Session | None = None,
) -> ToolResult:
    """Handle CRM search tool invocation."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Person, Organization

        results = {"persons": [], "organizations": []}

        if entity_type in ["all", "person"]:
            persons = (
                db.query(Person)
                .filter(
                    (Person.full_name.ilike(f"%{query}%"))
                    | (Person.title.ilike(f"%{query}%"))
                )
                .limit(limit)
                .all()
            )
            results["persons"] = [
                {
                    "id": str(p.id),
                    "full_name": p.full_name,
                    "title": p.title,
                    "company": p.organizations[0].organization.name if p.organizations else None,
                }
                for p in persons
            ]

        if entity_type in ["all", "organization"]:
            orgs = (
                db.query(Organization)
                .filter(
                    (Organization.name.ilike(f"%{query}%"))
                    | (Organization.category.ilike(f"%{query}%"))
                )
                .limit(limit)
                .all()
            )
            results["organizations"] = [
                {
                    "id": str(o.id),
                    "name": o.name,
                    "category": o.category,
                }
                for o in orgs
            ]

        total = len(results["persons"]) + len(results["organizations"])

        return ToolResult.success(
            {
                **results,
                "total": total,
                "query": query,
            },
        )
    except Exception as e:
        return ToolResult.create_error(f"CRM search failed: {str(e)}")


async def handle_suggest_update(
    entity_type: str,
    entity_id: str,
    field_name: str,
    suggested_value: str,
    source_url: str | None = None,
    confidence: float | None = None,
    conversation_id: str | None = None,
    append_to_notes: bool | None = None,  # None means auto-detect
    db: Session | None = None,
) -> ToolResult:
    """Handle suggestion creation tool invocation."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import AISuggestion, AISuggestionStatus
        from uuid import UUID

        # Validate entity exists
        if entity_type == "person":
            from app.models import Person

            entity = db.query(Person).filter(Person.id == UUID(entity_id)).first()
            if not entity:
                return ToolResult.create_error(f"Person {entity_id} not found")
            current_value = getattr(entity, field_name, None)
        elif entity_type == "organization":
            from app.models import Organization

            entity = (
                db.query(Organization)
                .filter(Organization.id == UUID(entity_id))
                .first()
            )
            if not entity:
                return ToolResult.create_error(f"Organization {entity_id} not found")
            current_value = getattr(entity, field_name, None)
        else:
            return ToolResult.create_error(f"Invalid entity type: {entity_type}")

        # For notes field, ALWAYS append to existing content by default when there's existing content
        # This prevents accidental data loss. Only replace if explicitly requested.
        final_suggested_value = suggested_value
        # Default to append=True for notes field when there's existing content
        should_append = append_to_notes if append_to_notes is not None else (field_name == "notes")

        if field_name == "notes" and should_append and current_value:
            # Smart detection: if AI mistakenly included existing notes in suggested_value,
            # extract only the new content
            new_content = suggested_value
            current_stripped = current_value.strip()
            suggested_stripped = suggested_value.strip()

            # Case 1: AI passed exactly the current value (no change)
            if suggested_stripped == current_stripped:
                return ToolResult.create_error(
                    "The suggested notes are the same as the current notes. "
                    "Please provide only the NEW content you want to add."
                )

            # Case 2: AI included current notes at the start - extract only the new part
            if suggested_stripped.startswith(current_stripped):
                new_content = suggested_stripped[len(current_stripped):].strip()
                # Remove common separators AI might have added
                for sep in ["\n\n", "\n", "---", "—", "-"]:
                    if new_content.startswith(sep):
                        new_content = new_content[len(sep):].strip()
                if not new_content:
                    return ToolResult.create_error(
                        "No new content detected. Please provide only the NEW content to add."
                    )

            # Append the (cleaned) new content to existing notes
            final_suggested_value = f"{current_value}\n\n---\n[AI Added]\n{new_content}"

        # Create suggestion
        suggestion = AISuggestion(
            conversation_id=UUID(conversation_id) if conversation_id else None,
            entity_type=entity_type,
            entity_id=UUID(entity_id),
            field_name=field_name,
            current_value=str(current_value) if current_value else None,
            suggested_value=final_suggested_value,
            confidence=confidence,
            source_url=source_url,
            status=AISuggestionStatus.pending,
        )
        db.add(suggestion)
        db.flush()

        return ToolResult.success(
            {
                "suggestion_id": str(suggestion.id),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "field_name": field_name,
                "current_value": str(current_value) if current_value else None,
                "suggested_value": final_suggested_value,
                "status": "pending",
                "appended": should_append and field_name == "notes" and current_value is not None,
            },
        )
    except Exception as e:
        import traceback
        error_details = f"Failed to create suggestion: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in handle_suggest_update: {error_details}", flush=True)
        return ToolResult.create_error(f"Failed to create suggestion: {str(e)}")


async def handle_add_employment(
    person_id: str,
    organization_name: str,
    title: str | None = None,
    is_current: bool = False,
    db: Session | None = None,
) -> ToolResult:
    """Handle adding employment history to a person."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Person, PersonEmployment, Organization
        from uuid import UUID
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"add_employment called: person_id={person_id}, org={organization_name}, title={title}")

        # Validate person exists
        try:
            pid = UUID(person_id)
        except ValueError:
            return ToolResult.create_error(f"Invalid person ID format: {person_id}")

        person = db.query(Person).filter(Person.id == pid).first()
        if not person:
            return ToolResult.create_error(f"Person {person_id} not found")

        # Truncate organization_name if too long (max 255 chars)
        if organization_name and len(organization_name) > 255:
            organization_name = organization_name[:252] + "..."

        # Truncate title if too long (max 255 chars)
        if title and len(title) > 255:
            title = title[:252] + "..."

        # Check if we already have this employment record
        existing = (
            db.query(PersonEmployment)
            .filter(
                PersonEmployment.person_id == pid,
                PersonEmployment.organization_name.ilike(organization_name),
            )
            .first()
        )
        if existing:
            logger.info(f"Employment already exists: {existing.id}")
            return ToolResult.success(
                {
                    "status": "already_exists",
                    "employment_id": str(existing.id),
                    "message": f"Employment at {organization_name} already exists for this person",
                },
            )

        # Try to find matching organization in database
        org = (
            db.query(Organization)
            .filter(Organization.name.ilike(f"%{organization_name}%"))
            .first()
        )

        # Create employment record
        employment = PersonEmployment(
            person_id=pid,
            organization_id=org.id if org else None,
            organization_name=organization_name,
            title=title,
            is_current=is_current,
        )
        db.add(employment)
        db.flush()

        logger.info(f"Employment created: {employment.id}")

        return ToolResult.success(
            {
                "status": "created",
                "employment_id": str(employment.id),
                "person_id": person_id,
                "organization_name": organization_name,
                "title": title,
                "is_current": is_current,
                "linked_to_org": org is not None,
            },
        )
    except Exception as e:
        import traceback
        error_details = f"Failed to add employment: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in handle_add_employment: {error_details}", flush=True)
        return ToolResult.create_error(f"Failed to add employment: {str(e)}")


async def handle_add_education(
    person_id: str,
    school_name: str,
    degree_type: str | None = None,
    field_of_study: str | None = None,
    graduation_year: int | None = None,
    db: Session | None = None,
) -> ToolResult:
    """Handle adding education history to a person."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Person, PersonEducation
        from uuid import UUID

        # Validate person exists
        person = db.query(Person).filter(Person.id == UUID(person_id)).first()
        if not person:
            return ToolResult.create_error(f"Person {person_id} not found")

        # Check if we already have this education record
        existing = (
            db.query(PersonEducation)
            .filter(
                PersonEducation.person_id == UUID(person_id),
                PersonEducation.school_name.ilike(school_name),
            )
            .first()
        )
        if existing:
            return ToolResult.success(
                {
                    "status": "already_exists",
                    "education_id": str(existing.id),
                    "message": f"Education at {school_name} already exists for this person",
                },
            )

        # Create education record
        education = PersonEducation(
            person_id=UUID(person_id),
            school_name=school_name,
            degree_type=degree_type,
            field_of_study=field_of_study,
            graduation_year=graduation_year,
        )
        db.add(education)
        db.flush()

        return ToolResult.success(
            {
                "status": "created",
                "education_id": str(education.id),
                "person_id": person_id,
                "school_name": school_name,
                "degree_type": degree_type,
                "field_of_study": field_of_study,
                "graduation_year": graduation_year,
            },
        )
    except Exception as e:
        return ToolResult.create_error(f"Failed to add education: {str(e)}")


async def handle_add_affiliated_person(
    organization_id: str,
    person_name: str,
    role: str | None = None,
    relationship_type: str = "key_person",
    is_current: bool = True,
    db: Session | None = None,
) -> ToolResult:
    """Handle adding an affiliated person (key people, founders, etc.) to an organization."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Organization, Person, PersonOrganization
        from app.models.organization import RelationshipType
        from uuid import UUID

        # Validate organization exists
        try:
            org_id = UUID(organization_id)
        except ValueError:
            return ToolResult.create_error(f"Invalid organization ID format: {organization_id}")

        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            return ToolResult.create_error(f"Organization {organization_id} not found")

        # Map string relationship type to enum
        rel_type_map = {
            "key_person": RelationshipType.key_person,
            "founder": RelationshipType.founder,
            "board_member": RelationshipType.board_member,
            "advisor": RelationshipType.advisor,
            "investor": RelationshipType.investor,
            "current_employee": RelationshipType.current_employee,
            "former_employee": RelationshipType.former_employee,
            "affiliated_with": RelationshipType.affiliated_with,
            "contact_at": RelationshipType.contact_at,
        }
        rel_type = rel_type_map.get(relationship_type.lower(), RelationshipType.key_person)

        # Try to find the person in the database
        person = (
            db.query(Person)
            .filter(Person.full_name.ilike(f"%{person_name}%"))
            .first()
        )

        # Check if this affiliation already exists
        if person:
            existing = (
                db.query(PersonOrganization)
                .filter(
                    PersonOrganization.person_id == person.id,
                    PersonOrganization.organization_id == org_id,
                )
                .first()
            )
            if existing:
                return ToolResult.success(
                    {
                        "status": "already_exists",
                        "affiliation_id": str(existing.id),
                        "message": f"{person_name} is already affiliated with {org.name}",
                    },
                )

        # Check for unlinked person name reference
        existing_unlinked = (
            db.query(PersonOrganization)
            .filter(
                PersonOrganization.organization_id == org_id,
                PersonOrganization.person_name.ilike(person_name),
                PersonOrganization.person_id.is_(None),
            )
            .first()
        )
        if existing_unlinked:
            return ToolResult.success(
                {
                    "status": "already_exists",
                    "affiliation_id": str(existing_unlinked.id),
                    "message": f"{person_name} is already listed as affiliated with {org.name}",
                },
            )

        # Truncate role if too long (max 300 chars per schema)
        if role and len(role) > 300:
            role = role[:297] + "..."

        # Create the PersonOrganization record
        affiliation = PersonOrganization(
            person_id=person.id if person else None,
            organization_id=org_id,
            person_name=person_name if not person else None,  # Only store name if no linked person
            relationship=rel_type,
            role=role,
            is_current=is_current,
        )
        db.add(affiliation)
        db.flush()

        return ToolResult.success(
            {
                "status": "created",
                "affiliation_id": str(affiliation.id),
                "organization_id": organization_id,
                "organization_name": org.name,
                "person_name": person_name,
                "person_id": str(person.id) if person else None,
                "linked_to_person": person is not None,
                "relationship_type": rel_type.value,
                "role": role,
                "is_current": is_current,
            },
        )
    except Exception as e:
        import traceback
        error_details = f"Failed to add affiliated person: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in handle_add_affiliated_person: {error_details}", flush=True)
        return ToolResult.create_error(f"Failed to add affiliated person: {str(e)}")


async def handle_add_relationship(
    person_id: str,
    related_person_name: str,
    relationship_type: str,
    context: str | None = None,
    db: Session | None = None,
) -> ToolResult:
    """Handle adding a relationship between two people."""
    if db is None:
        return ToolResult.create_error("Database session required")

    try:
        from app.models import Person, PersonRelationship
        from app.models.relationship_type import RelationshipType
        from uuid import UUID

        # Validate person exists
        person = db.query(Person).filter(Person.id == UUID(person_id)).first()
        if not person:
            return ToolResult.create_error(f"Person {person_id} not found")

        # Try to find the related person
        related_person = (
            db.query(Person)
            .filter(Person.full_name.ilike(f"%{related_person_name}%"))
            .first()
        )

        # If related person not found, create them
        if not related_person:
            related_person = Person(
                full_name=related_person_name,
                notes=f"Created by AI as a relationship contact for {person.full_name}",
            )
            db.add(related_person)
            db.flush()
            created_new_person = True
        else:
            created_new_person = False

        # Find or create the relationship type
        rel_type = (
            db.query(RelationshipType)
            .filter(RelationshipType.name.ilike(f"%{relationship_type}%"))
            .first()
        )

        # If no matching type, create a custom one
        if not rel_type:
            rel_type = RelationshipType(
                name=relationship_type,
                inverse_name=relationship_type,  # Symmetric by default
                is_system=False,
            )
            db.add(rel_type)
            db.flush()
            created_new_type = True
        else:
            created_new_type = False

        # Check if relationship already exists
        existing = (
            db.query(PersonRelationship)
            .filter(
                PersonRelationship.person_id == person.id,
                PersonRelationship.related_person_id == related_person.id,
                PersonRelationship.relationship_type_id == rel_type.id,
            )
            .first()
        )
        if existing:
            return ToolResult.success(
                {
                    "status": "already_exists",
                    "relationship_id": str(existing.id),
                    "message": f"Relationship already exists between {person.full_name} and {related_person.full_name}",
                },
            )

        # Create the relationship
        relationship = PersonRelationship(
            person_id=person.id,
            related_person_id=related_person.id,
            relationship_type_id=rel_type.id,
            context_text=context,
        )
        db.add(relationship)

        # Create inverse relationship if the type has an inverse
        if rel_type.inverse_name:
            inverse_type = (
                db.query(RelationshipType)
                .filter(RelationshipType.name == rel_type.inverse_name)
                .first()
            )
            if inverse_type:
                inverse_rel = PersonRelationship(
                    person_id=related_person.id,
                    related_person_id=person.id,
                    relationship_type_id=inverse_type.id,
                    context_text=context,
                )
                db.add(inverse_rel)

        db.flush()

        return ToolResult.success(
            {
                "status": "created",
                "relationship_id": str(relationship.id),
                "person_id": person_id,
                "person_name": person.full_name,
                "related_person_id": str(related_person.id),
                "related_person_name": related_person.full_name,
                "relationship_type": rel_type.name,
                "context": context,
                "created_new_person": created_new_person,
                "created_new_type": created_new_type,
            },
        )
    except Exception as e:
        return ToolResult.create_error(f"Failed to add relationship: {str(e)}")


# Tool definitions
SEARCH_TOOLS = [
    Tool(
        name="web_search",
        description=(
            "Search the web for information. Use this to find recent news, "
            "articles, and general information about people, companies, "
            "or topics. IMPORTANT: When searching for a person, construct a descriptive query "
            "with their name, title/role, AND organization to find content specifically about them. "
            "Example: 'Fred Wilson venture capitalist Union Square Ventures' "
            "NOT just 'Fred Wilson' or 'Fred Wilson Union Square Ventures'."
        ),
        parameters=[
            ToolParameter(
                name="query",
                description="Descriptive search query - for people include their name, title/role, and organization",
                type="string",
            ),
            ToolParameter(
                name="max_results",
                description="Maximum number of results to return (1-10)",
                type="number",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="include_news",
                description="Include news results in addition to web results",
                type="boolean",
                required=False,
                default=False,
            ),
        ],
        handler=handle_web_search,
        category="search",
    ),
    Tool(
        name="youtube_search",
        description=(
            "Search YouTube for videos. Use this to find talks, interviews, "
            "presentations, and other video content about people or topics. "
            "IMPORTANT: When searching for a person, construct a descriptive query with their "
            "name, title/role, AND organization to find content specifically about them. "
            "Example: 'Fred Wilson venture capitalist Union Square Ventures interview' "
            "NOT just 'Fred Wilson interview' or 'Fred Wilson Union Square Ventures'."
        ),
        parameters=[
            ToolParameter(
                name="query",
                description="Descriptive search query - for people include their name, title/role, and organization",
                type="string",
            ),
            ToolParameter(
                name="max_results",
                description="Maximum number of results to return (1-10)",
                type="number",
                required=False,
                default=5,
            ),
        ],
        handler=handle_youtube_search,
        category="search",
    ),
    Tool(
        name="podcast_search",
        description=(
            "Search for podcast episodes. Use this to find podcast "
            "appearances and interviews by or about people. "
            "IMPORTANT: When searching for a person, construct a descriptive query with their "
            "name, title/role, AND organization to find content specifically about them. "
            "Example: 'Fred Wilson venture capitalist Union Square Ventures podcast' "
            "NOT just 'Fred Wilson podcast' or 'Fred Wilson Union Square Ventures podcast'."
        ),
        parameters=[
            ToolParameter(
                name="query",
                description="Descriptive search query - for people include their name, title/role, and organization",
                type="string",
            ),
            ToolParameter(
                name="max_results",
                description="Maximum number of results to return (1-10)",
                type="number",
                required=False,
                default=5,
            ),
        ],
        handler=handle_podcast_search,
        category="search",
    ),
]

CRM_TOOLS = [
    Tool(
        name="lookup_person",
        description=(
            "Look up a person in the CRM database by ID or name. "
            "Returns their profile information including title, company, "
            "location, and notes."
        ),
        parameters=[
            ToolParameter(
                name="person_id",
                description="The UUID of the person to look up",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="name",
                description="The name to search for (partial match)",
                type="string",
                required=False,
            ),
        ],
        handler=handle_lookup_person,
        category="crm",
    ),
    Tool(
        name="lookup_organization",
        description=(
            "Look up an organization in the CRM database by ID or name. "
            "Returns company information including category, type, "
            "and description."
        ),
        parameters=[
            ToolParameter(
                name="org_id",
                description="The UUID of the organization to look up",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="name",
                description="The name to search for (partial match)",
                type="string",
                required=False,
            ),
        ],
        handler=handle_lookup_organization,
        category="crm",
    ),
    Tool(
        name="search_crm",
        description=(
            "Search the CRM database for people and organizations. "
            "Returns matching records based on the search query."
        ),
        parameters=[
            ToolParameter(
                name="query",
                description="The search query",
                type="string",
            ),
            ToolParameter(
                name="entity_type",
                description="Type of entity to search: 'person', 'organization', or 'all'",
                type="string",
                required=False,
                enum=["all", "person", "organization"],
                default="all",
            ),
            ToolParameter(
                name="limit",
                description="Maximum number of results per entity type",
                type="number",
                required=False,
                default=10,
            ),
        ],
        handler=handle_search_crm,
        category="crm",
    ),
    Tool(
        name="suggest_update",
        description=(
            "Create a suggestion to update a field on a person or "
            "organization record. The suggestion will be saved for "
            "user review and approval. IMPORTANT: For the notes field, "
            "pass ONLY the NEW content to add - the system automatically "
            "appends it to existing notes. Do NOT include the existing notes "
            "in suggested_value."
        ),
        parameters=[
            ToolParameter(
                name="entity_type",
                description="Type of entity: 'person' or 'organization'",
                type="string",
                enum=["person", "organization"],
            ),
            ToolParameter(
                name="entity_id",
                description="The UUID of the entity to update",
                type="string",
            ),
            ToolParameter(
                name="field_name",
                description="The field to update (e.g., 'title', 'company', 'notes')",
                type="string",
            ),
            ToolParameter(
                name="suggested_value",
                description="The NEW value to set. For notes: pass ONLY the new content to add, NOT the existing notes",
                type="string",
            ),
            ToolParameter(
                name="source_url",
                description="URL source for this information",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="confidence",
                description="Confidence score from 0.0 to 1.0",
                type="number",
                required=False,
            ),
            ToolParameter(
                name="append_to_notes",
                description="If true and field_name is 'notes', append to existing notes instead of replacing. Always use this for notes!",
                type="boolean",
                required=False,
                default=True,
            ),
        ],
        handler=handle_suggest_update,
        category="crm",
        requires_confirmation=True,
    ),
    Tool(
        name="add_employment",
        description=(
            "Add an employment/work history entry to a person's profile. "
            "Use this when you learn about a person's current or past job. "
            "This creates a record directly without requiring approval."
        ),
        parameters=[
            ToolParameter(
                name="person_id",
                description="The UUID of the person",
                type="string",
            ),
            ToolParameter(
                name="organization_name",
                description="Name of the company/organization",
                type="string",
            ),
            ToolParameter(
                name="title",
                description="Job title at this organization",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="is_current",
                description="Whether this is their current job",
                type="boolean",
                required=False,
                default=False,
            ),
        ],
        handler=handle_add_employment,
        category="crm",
    ),
    Tool(
        name="add_education",
        description=(
            "Add an education entry to a person's profile. "
            "Use this when you learn about a person's educational background. "
            "This creates a record directly without requiring approval."
        ),
        parameters=[
            ToolParameter(
                name="person_id",
                description="The UUID of the person",
                type="string",
            ),
            ToolParameter(
                name="school_name",
                description="Name of the school/university",
                type="string",
            ),
            ToolParameter(
                name="degree_type",
                description="Type of degree: BA, BS, MA, MS, MBA, PhD, JD, MD, or Other",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="field_of_study",
                description="Major or field of study",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="graduation_year",
                description="Year of graduation",
                type="number",
                required=False,
            ),
        ],
        handler=handle_add_education,
        category="crm",
    ),
    Tool(
        name="add_relationship",
        description=(
            "Add a relationship between two people. "
            "Use this when you learn about personal or professional relationships "
            "like 'married to', 'friends with', 'worked together', 'family member', etc. "
            "If the related person doesn't exist, they will be created automatically."
        ),
        parameters=[
            ToolParameter(
                name="person_id",
                description="The UUID of the main person (the one whose profile you're updating)",
                type="string",
            ),
            ToolParameter(
                name="related_person_name",
                description="Full name of the related person (e.g., 'Jane Smith')",
                type="string",
            ),
            ToolParameter(
                name="relationship_type",
                description="Type of relationship: 'Spouse', 'Family Member', 'Friend', 'Worked Together', 'College Classmate', 'Reports To', 'Manages', 'Introduced By', or any custom type",
                type="string",
            ),
            ToolParameter(
                name="context",
                description="Additional context about the relationship (e.g., 'Met at Stanford in 2015')",
                type="string",
                required=False,
            ),
        ],
        handler=handle_add_relationship,
        category="crm",
    ),
    Tool(
        name="add_affiliated_person",
        description=(
            "Add an affiliated person to an organization's 'Affiliated People' section. "
            "IMPORTANT: This tool works even if the person does NOT exist in the CRM yet! "
            "It will store their name as an unlinked reference that can be linked later. "
            "Use this when you learn about key people, founders, board members, executives, "
            "or other people associated with an organization. "
            "You do NOT need to create a contact first - just call this tool with their name. "
            "When researching organizations, ALWAYS use this tool for key people instead of Notes."
        ),
        parameters=[
            ToolParameter(
                name="organization_id",
                description="The UUID of the organization",
                type="string",
            ),
            ToolParameter(
                name="person_name",
                description="Full name of the person (e.g., 'John Smith')",
                type="string",
            ),
            ToolParameter(
                name="role",
                description="Their role/title at the organization (e.g., 'CEO', 'Co-Founder', 'Managing Partner')",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="relationship_type",
                description="Type: 'founder', 'key_person', 'board_member', 'advisor', 'investor', 'current_employee', 'former_employee', 'affiliated_with'",
                type="string",
                required=False,
                enum=["founder", "key_person", "board_member", "advisor", "investor", "current_employee", "former_employee", "affiliated_with"],
                default="key_person",
            ),
            ToolParameter(
                name="is_current",
                description="Whether they are currently in this role",
                type="boolean",
                required=False,
                default=True,
            ),
        ],
        handler=handle_add_affiliated_person,
        category="crm",
    ),
]


def get_default_tools() -> list[Tool]:
    """Get all default tools."""
    return SEARCH_TOOLS + CRM_TOOLS


def create_tool_registry(
    include_search: bool = True,
    include_crm: bool = True,
) -> ToolRegistry:
    """Create a tool registry with specified tool categories."""
    registry = ToolRegistry()

    if include_search:
        for tool in SEARCH_TOOLS:
            registry.register(tool)

    if include_crm:
        for tool in CRM_TOOLS:
            registry.register(tool)

    return registry
