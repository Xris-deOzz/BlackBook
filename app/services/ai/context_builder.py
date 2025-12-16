"""
Context builder for AI conversations.

Builds rich context from CRM data (persons, organizations, interactions)
while respecting privacy settings and token limits.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    Person,
    Organization,
    AIDataAccessSettings,
)
from app.services.ai.privacy_filter import (
    filter_person_for_ai,
    filter_organization_for_ai,
    strip_sensitive_data,
)
from app.services.ai.token_utils import estimate_tokens
from app.config import get_settings


class ContextBuilder:
    """
    Builds AI context from CRM data.

    Respects data access settings and token limits while providing
    rich context for AI conversations.
    """

    def __init__(self, db: Session, max_tokens: int | None = None):
        """
        Initialize context builder.

        Args:
            db: Database session
            max_tokens: Maximum tokens for context (defaults to config value)
        """
        self.db = db
        settings = get_settings()
        self.max_tokens = max_tokens or settings.ai_max_context_tokens
        self._data_access: AIDataAccessSettings | None = None

    @property
    def data_access(self) -> AIDataAccessSettings:
        """Get data access settings (cached)."""
        if self._data_access is None:
            self._data_access = AIDataAccessSettings.get_settings(self.db)
        return self._data_access

    def build_person_context(self, person_id: UUID) -> str:
        """
        Build context for a person.

        Args:
            person_id: UUID of the person

        Returns:
            Formatted context string
        """
        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            return ""

        context_parts = []

        # Basic info (always included) - include ID for tool calls
        # Use str() to ensure proper UUID string format
        context_parts.append(f"Person ID (use this exact value for tool calls): {str(person.id)}")
        context_parts.append(f"Person Name: {person.full_name}")

        # Build role/title info
        role_title = person.title
        org_name = None
        org_category = None

        if person.organizations:
            primary_org = person.organizations[0].organization
            org_name = primary_org.name
            org_category = primary_org.category

        if role_title:
            context_parts.append(f"Title/Role: {role_title}")

        if org_name:
            context_parts.append(f"Organization: {org_name}")
            if org_category:
                context_parts.append(f"Category: {org_category}")

        # Create a search hint for the AI to use when searching for this person
        search_terms = [person.full_name]
        if role_title:
            search_terms.append(role_title)
        if org_name:
            search_terms.append(org_name)
        context_parts.append(f"SEARCH HINT: When searching for this person, use: \"{' '.join(search_terms)}\"")

        # LinkedIn (if allowed)
        if self.data_access.allow_linkedin and person.linkedin:
            context_parts.append(f"LinkedIn: {person.linkedin}")

        # Notes (if allowed)
        if self.data_access.allow_notes and person.notes:
            filtered_notes = strip_sensitive_data(person.notes)
            context_parts.append(f"Notes: {filtered_notes}")

        # Tags (if allowed)
        if self.data_access.allow_tags and person.tags:
            tag_names = [tag.name for tag in person.tags]
            if tag_names:
                context_parts.append(f"Tags: {', '.join(tag_names)}")

        # Employment/Work History - explicitly show what's stored so AI knows what to add
        if hasattr(person, 'employment') and person.employment:
            emp_list = []
            for emp in person.employment:
                emp_str = emp.organization_name
                if emp.title:
                    emp_str = f"{emp.title} at {emp_str}"
                if emp.is_current:
                    emp_str += " (current)"
                emp_list.append(emp_str)
            context_parts.append(f"Work Experience / Employment History (already stored): {'; '.join(emp_list)}")
        else:
            context_parts.append("Work Experience / Employment History: None stored - use add_employment tool to add jobs/work history")

        # Education History - explicitly show what's stored
        if hasattr(person, 'education') and person.education:
            edu_list = []
            for edu in person.education:
                edu_str = edu.school_name
                if edu.degree_type and edu.field_of_study:
                    edu_str = f"{edu.degree_type} in {edu.field_of_study} from {edu_str}"
                elif edu.degree_type:
                    edu_str = f"{edu.degree_type} from {edu_str}"
                if edu.graduation_year:
                    edu_str += f" ({edu.graduation_year})"
                edu_list.append(edu_str)
            context_parts.append(f"Education History (already stored): {'; '.join(edu_list)}")
        else:
            context_parts.append("Education History: None stored - use add_education tool to add education")

        # Relationships - include IDs so AI can reference related people
        if hasattr(person, 'relationships_from') and person.relationships_from:
            rel_list = []
            for rel in person.relationships_from:
                if rel.related_person:
                    # Include person ID so AI can update notes/info on related people
                    rel_type_name = rel.relationship_type.name if rel.relationship_type else "Related"
                    rel_list.append(f"{rel.related_person.full_name} (ID: {str(rel.related_person.id)}, {rel_type_name})")
            if rel_list:
                context_parts.append(f"Relationships (already stored): {'; '.join(rel_list)}")
        else:
            context_parts.append("Relationships: None stored - use add_relationship tool to add relationships")

        # Build context string
        context = "\n".join(context_parts)

        # Truncate if exceeds token limit
        return self._truncate_to_tokens(context, self.max_tokens // 2)

    def build_organization_context(self, org_id: UUID) -> str:
        """
        Build context for an organization.

        Args:
            org_id: UUID of the organization

        Returns:
            Formatted context string
        """
        org = self.db.query(Organization).filter_by(id=org_id).first()
        if not org:
            return ""

        context_parts = []

        # Basic info - include ID for tool calls
        context_parts.append(f"Organization ID (use this exact value for tool calls): {str(org.id)}")
        context_parts.append(f"Organization Name: {org.name}")

        if org.category:
            context_parts.append(f"Category: {org.category}")

        if org.org_type:
            context_parts.append(f"Type: {org.org_type.value}")

        if org.website:
            context_parts.append(f"Website: {org.website}")

        if org.description:
            context_parts.append(f"Description: {org.description}")

        # Notes (if allowed)
        if self.data_access.allow_notes and org.notes:
            filtered_notes = strip_sensitive_data(org.notes)
            context_parts.append(f"Notes: {filtered_notes}")

        # Tags (if allowed)
        if self.data_access.allow_tags and org.tags:
            tag_names = [tag.name for tag in org.tags]
            if tag_names:
                context_parts.append(f"Tags: {', '.join(tag_names)}")

        # Affiliated People / Key People - explicitly show status so AI knows what to add
        if org.affiliated_persons:
            people_list = []
            for ap in org.affiliated_persons[:10]:  # Limit to 10
                person_str = ap.person.full_name if ap.person else ap.person_name
                if ap.role:
                    person_str = f"{person_str} ({ap.role})"
                people_list.append(person_str)
            context_parts.append(f"Affiliated People (already stored): {'; '.join(people_list)}")
        else:
            context_parts.append("Affiliated People: None stored - use add_affiliated_person tool to add key people, founders, executives, board members")

        context = "\n".join(context_parts)
        return self._truncate_to_tokens(context, self.max_tokens // 2)

    def build_system_prompt(
        self,
        person_id: UUID | None = None,
        org_id: UUID | None = None,
    ) -> str:
        """
        Build the system prompt for AI conversation.

        Args:
            person_id: Optional person context
            org_id: Optional organization context

        Returns:
            System prompt string
        """
        base_prompt = """You are a helpful AI research assistant for a personal CRM called Perun's BlackBook.
Your role is to help the user research and learn more about their contacts and organizations.

Guidelines:
- Be concise and professional
- Focus on providing actionable insights
- When researching online, cite your sources with URLs
- ALWAYS include source URLs when adding information from search results to notes
  Example: "Fred Wilson discussed entrepreneurship in an interview (https://youtube.com/watch?v=...)"
- If you're unsure about something, say so
- Never fabricate information about contacts
- Respect privacy - don't share sensitive information

RESEARCH TOOLS - USE THESE FOR ONLINE RESEARCH:

When the user asks you to research someone, prepare a dossier, or find information, you MUST use the search tools:

1. **web_search** - Search the web for news, articles, and general information
   Parameters: query (required), max_results (optional, default 5), include_news (optional)
   Use for: Company info, news articles, recent developments, general research, AUM, key people, deals

2. **youtube_search** - Search YouTube for videos, talks, and interviews
   Parameters: query (required), max_results (optional, default 5)
   Use for: Conference talks, interviews, presentations, video content

3. **podcast_search** - Search for podcast episodes
   Parameters: query (required), max_results (optional, default 5)
   Use for: Podcast appearances, audio interviews

IMPORTANT SEARCH TIPS:
- When searching for a person, ALWAYS construct a descriptive search query using:
  1. Their full name
  2. Their title/role (e.g., "venture capitalist", "CEO", "Managing Partner")
  3. Their organization/company name
  Example: Search for "Fred Wilson venture capitalist Union Square Ventures interview"
  NOT just "Fred Wilson interview" or even "Fred Wilson Union Square Ventures"
- For companies: search for "CompanyName AUM" or "CompanyName key people" or "CompanyName investments"
- If web_search returns an error about API keys, inform the user:
  "Web search is not available. Please configure the Brave Search API key in Settings > AI Providers to enable online research."
- If you cannot find information via search tools, clearly state what you searched for and that no results were found.
  Do NOT pretend to have information you don't have.

CRITICAL - HOW TO UPDATE PROFILES:

You MUST use the function calling tools provided to update profiles. DO NOT output JSON in your text responses.
The system will NOT parse JSON from your text - only function calls work.

AVAILABLE TOOLS (use these via function calling):

1. **add_employment** - Add work experience / employment / job history entries
   ALWAYS use this when you learn about someone's current or past jobs, work experience, or employment.
   Parameters: person_id, organization_name, title (optional), is_current (optional)
   Example trigger: "He worked at Google as a Software Engineer"

2. **add_education** - Add education entries
   ALWAYS use this when you learn about educational background.
   Parameters: person_id, school_name, degree_type (optional), field_of_study (optional), graduation_year (optional)
   Example trigger: "She has an MBA from Harvard"

3. **add_relationship** - Add relationships between people
   ALWAYS use this when you learn about personal/professional relationships.
   Parameters: person_id, related_person_name, relationship_type, context (optional)
   Relationship types: Spouse, Family Member, Friend, Worked Together, College Classmate, etc.
   Example trigger: "His wife is named Sarah" → use add_relationship with type "Spouse"
   If the related person doesn't exist, they'll be created automatically.

4. **add_affiliated_person** - Add key people/executives/founders to an organization
   ALWAYS use this when researching an organization and you find key people, founders, executives, board members, etc.
   Parameters: organization_id, person_name, role (optional), relationship_type (optional), is_current (optional)
   Relationship types: founder, key_person, board_member, advisor, investor, current_employee, former_employee
   Example triggers:
   - "The founders are John Smith and Jane Doe" → call add_affiliated_person twice with relationship_type="founder"
   - "CEO is Bob Johnson" → call add_affiliated_person with role="CEO" and relationship_type="key_person"
   ⚠️ NEVER put key people/founders/executives into Notes - ALWAYS use add_affiliated_person!

5. **suggest_update** - Update basic profile fields (title, linkedin, twitter, website, location, notes)
   Parameters: entity_type, entity_id, field_name, suggested_value

   ⚠️ NEVER use suggest_update for employment/job/work history - use add_employment instead!
   ⚠️ NEVER use suggest_update for education - use add_education instead!
   ⚠️ NEVER use suggest_update for relationships - use add_relationship instead!
   ⚠️ NEVER use suggest_update for key people/founders/executives on organizations - use add_affiliated_person instead!

   suggest_update is ONLY for: title, linkedin, twitter, website, location, or misc notes that don't fit structured data.

   CRITICAL FOR NOTES: Pass ONLY the NEW content you want to add in suggested_value.
   The system will automatically append it to existing notes. Do NOT include existing notes in your call.
   Example: User says "add FINRA licenses to notes" → call suggest_update with suggested_value="FINRA licenses: Series 7, 63, 24"
   (NOT suggested_value="Anton and Sue have 2 kids. FINRA licenses...")

   IMPORTANT for notes about family/relationships:
   - When user says something like "they have 2 kids" referring to the main person and their spouse,
     add the note to the MAIN person's profile (the one in Current Person Context).
   - Use the Person ID from the context (not the spouse's ID).
   - For related people, you can use the IDs shown in the Relationships section.

MANDATORY RULES:
- NEVER output JSON suggestions in your text response - the system ignores text JSON
- ALWAYS use the function calling mechanism to invoke tools
- When user provides work/employment/job info → ALWAYS call add_employment tool (NOT suggest_update to notes!)
- When user provides education info → ALWAYS call add_education tool (NOT suggest_update to notes!)
- When user mentions relationships (wife, husband, family, friend) → ALWAYS call add_relationship tool
- When researching organizations and finding key people/founders/executives → ALWAYS call add_affiliated_person (NOT notes!)
- Only use suggest_update for: title, linkedin, twitter, website, location, or miscellaneous notes
- You can call multiple tools in a single response - call add_employment multiple times for multiple jobs
- You can call add_affiliated_person multiple times for multiple key people
- If user pastes a LinkedIn work history with multiple jobs, call add_employment once for EACH job separately

IMPORTANT: The context below shows what is ACTUALLY STORED in the database.
- If "Work Experience / Employment History: None stored" → you MUST call add_employment to add any work/job/employment history
- If "Education History: None stored" → you MUST call add_education to add any education
- If "Affiliated People: None stored" → you MUST call add_affiliated_person to add key people/founders/executives
- The "Organization" field is just a quick reference - it does NOT mean work experience is stored
- When the user asks you to add information, CHECK the context to see if it's already stored. If not, USE THE TOOL.

⚠️ CRITICAL FOR ORGANIZATIONS:
When researching an organization and you find information about key people, founders, executives, partners, or board members:
1. DO NOT put this information in Notes
2. MUST call add_affiliated_person for EACH key person you discover
3. The add_affiliated_person tool DOES NOT require the person to exist in the CRM! It stores their name as a reference.
4. You do NOT need to create a contact first - just call add_affiliated_person with their name
5. Call add_affiliated_person multiple times - once per person
6. YOU HAVE THE ABILITY TO CALL THESE TOOLS - do NOT say "please add manually" or "I cannot update directly"

⚠️ AFTER DOING WEB SEARCH - MANDATORY NEXT STEP:
If you searched the web and found key people/founders/executives for an organization:
- You MUST immediately call add_affiliated_person for each person found
- Do NOT just list them in your text response
- Do NOT ask the user to add them manually
- CALL THE TOOL YOURSELF - you have the capability!

Example: If you find "TPG was founded by David Bonderman and Jim Coulter":
Use the Organization ID from the context above and call:
- add_affiliated_person(organization_id="<ORG_ID>", person_name="David Bonderman", role="Co-Founder", relationship_type="founder")
- add_affiliated_person(organization_id="<ORG_ID>", person_name="Jim Coulter", role="Co-Founder", relationship_type="founder")

NEVER say "please add these individuals manually" - YOU call the add_affiliated_person tool!"""

        # Add entity context
        context_parts = [base_prompt]

        if person_id:
            person_context = self.build_person_context(person_id)
            if person_context:
                context_parts.append(f"\n\nCurrent Person Context:\n{person_context}")

        if org_id:
            org_context = self.build_organization_context(org_id)
            if org_context:
                context_parts.append(f"\n\nCurrent Organization Context:\n{org_context}")

        return "\n".join(context_parts)

    def build_conversation_context(
        self,
        messages: list[dict[str, str]],
        person_id: UUID | None = None,
        org_id: UUID | None = None,
    ) -> list[dict[str, str]]:
        """
        Build full conversation context including system prompt.

        Args:
            messages: List of conversation messages
            person_id: Optional person context
            org_id: Optional organization context

        Returns:
            Messages list with system prompt prepended
        """
        system_prompt = self.build_system_prompt(person_id, org_id)

        # Prepend system message
        full_messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation messages (filtering any sensitive data in user messages)
        for msg in messages:
            filtered_msg = {
                "role": msg["role"],
                "content": strip_sensitive_data(msg["content"]) if msg["role"] == "user" else msg["content"],
            }
            full_messages.append(filtered_msg)

        return full_messages

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Input text
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text
        """
        current_tokens = estimate_tokens(text)
        if current_tokens <= max_tokens:
            return text

        # Simple truncation - cut by ratio
        ratio = max_tokens / current_tokens
        chars_to_keep = int(len(text) * ratio * 0.9)  # 10% buffer
        return text[:chars_to_keep] + "..."

    def person_to_dict(self, person: Person) -> dict[str, Any]:
        """
        Convert person model to filtered dictionary.

        Args:
            person: Person model instance

        Returns:
            Filtered dictionary safe for AI
        """
        data = {
            "id": str(person.id),
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "title": person.title,
        }

        if person.organizations:
            data["organization"] = person.organizations[0].organization.name

        if self.data_access.allow_linkedin:
            data["linkedin_url"] = person.linkedin

        if self.data_access.allow_notes:
            data["notes"] = person.notes

        if self.data_access.allow_tags and person.tags:
            data["tags"] = [t.name for t in person.tags]

        return filter_person_for_ai(data)

    def organization_to_dict(self, org: Organization) -> dict[str, Any]:
        """
        Convert organization model to filtered dictionary.

        Args:
            org: Organization model instance

        Returns:
            Filtered dictionary safe for AI
        """
        data = {
            "id": str(org.id),
            "name": org.name,
            "category": org.category,
            "org_type": org.org_type.value if org.org_type else None,
            "website": org.website,
            "description": org.description,
        }

        if self.data_access.allow_notes:
            data["notes"] = org.notes

        if self.data_access.allow_tags and org.tags:
            data["tags"] = [t.name for t in org.tags]

        return filter_organization_for_ai(data)
