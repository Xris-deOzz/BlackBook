"""
Person research workflow.

Automated research on individuals, finding career updates,
news mentions, talks, and podcast appearances.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Person, AISuggestion, AISuggestionStatus
from app.services.ai.base_provider import ChatMessage
from app.services.ai.provider_factory import ProviderFactory
from app.services.ai.research.workflow import (
    ResearchWorkflow,
    ResearchConfig,
    ResearchResult,
    ResearchStatus,
    ResearchDepth,
    ResearchSource,
    ResearchFinding,
)


class PersonResearcher(ResearchWorkflow):
    """
    Research workflow for individuals.

    Searches for and analyzes:
    - Career updates (new roles, promotions)
    - News mentions
    - Conference talks and presentations
    - Podcast appearances
    - Social media activity
    """

    async def research(
        self,
        entity_id: UUID,
        config: ResearchConfig | None = None,
    ) -> ResearchResult:
        """
        Execute research on a person.

        Args:
            entity_id: UUID of the person to research
            config: Research configuration

        Returns:
            ResearchResult with findings and sources
        """
        config = config or ResearchConfig()
        started_at = datetime.utcnow()

        # Load person from database
        person = self.db.query(Person).filter(Person.id == entity_id).first()
        if not person:
            return ResearchResult(
                entity_type="person",
                entity_id=entity_id,
                entity_name="Unknown",
                status=ResearchStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                config=config,
                error=f"Person {entity_id} not found",
            )

        result = ResearchResult(
            entity_type="person",
            entity_id=entity_id,
            entity_name=person.full_name,
            status=ResearchStatus.IN_PROGRESS,
            started_at=started_at,
            config=config,
        )

        try:
            # Generate search queries
            queries = await self.get_search_queries(entity_id, config)

            # Execute searches
            all_sources: list[ResearchSource] = []
            for query in queries:
                sources = await self._search_all_sources(query, config)
                all_sources.extend(sources)

            # Deduplicate sources
            result.sources = self._deduplicate_sources(all_sources)

            # Analyze findings with AI
            if result.sources:
                findings = await self._analyze_findings(person, result.sources, config)
                result.findings = findings

                # Generate summary
                result.summary = await self._generate_summary(
                    person, result.sources, findings, config
                )

                # Create suggestions if configured
                if config.auto_suggest_updates:
                    await self._create_suggestions(person, findings)

            result.status = ResearchStatus.COMPLETED
            result.completed_at = datetime.utcnow()

        except Exception as e:
            result.status = ResearchStatus.FAILED
            result.completed_at = datetime.utcnow()
            result.error = str(e)

        return result

    async def get_search_queries(
        self,
        entity_id: UUID,
        config: ResearchConfig,
    ) -> list[str]:
        """
        Generate search queries for a person.

        Args:
            entity_id: UUID of the person
            config: Research configuration

        Returns:
            List of search queries
        """
        person = self.db.query(Person).filter(Person.id == entity_id).first()
        if not person:
            return []

        queries = []
        name = person.full_name

        # Basic name search
        queries.append(f'"{name}"')

        # Add company context if available
        if person.organizations:
            company_name = person.organizations[0].organization.name
            queries.append(f'"{name}" {company_name}')

        # Depth-based additional queries
        if config.depth in [ResearchDepth.STANDARD, ResearchDepth.DEEP]:
            # Career and professional queries
            if person.title:
                queries.append(f'"{name}" {person.title}')

            # News mentions
            queries.append(f'"{name}" announcement OR news')

        if config.depth == ResearchDepth.DEEP:
            # Talk and presentation queries
            queries.append(f'"{name}" talk OR presentation OR keynote OR conference')

            # Interview queries
            queries.append(f'"{name}" interview')

            # LinkedIn activity (if we have their URL)
            if person.linkedin:
                linkedin_id = person.linkedin.rstrip("/").split("/")[-1]
                queries.append(f'"{name}" {linkedin_id}')

        return queries

    async def _analyze_findings(
        self,
        person: Person,
        sources: list[ResearchSource],
        config: ResearchConfig,
    ) -> list[ResearchFinding]:
        """
        Use AI to analyze sources and extract findings.

        Args:
            person: Person being researched
            sources: Sources found during research
            config: Research configuration

        Returns:
            List of findings
        """
        findings: list[ResearchFinding] = []

        # Skip AI analysis if no provider configured
        if not config.provider_name:
            # Try to get default provider
            available = ProviderFactory.get_available_providers(self.db)
            if not available:
                return findings
            config.provider_name = available[0]

        try:
            provider = ProviderFactory.get_provider(config.provider_name, self.db)
        except Exception:
            return findings

        # Prepare source summaries for analysis
        source_text = "\n\n".join([
            f"Source: {s.title}\nURL: {s.url}\n{s.snippet}"
            for s in sources[:15]  # Limit to avoid token limits
        ])

        # Build prompt for analysis
        company_name = person.organizations[0].organization.name if person.organizations else 'Unknown'
        current_info = f"""
Current CRM Information:
- Name: {person.full_name}
- Title: {person.title or 'Unknown'}
- Company: {company_name}
- Location: {person.location or 'Unknown'}
"""

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a research analyst helping to update a CRM database. "
                    "Analyze the search results and identify any updates or new information "
                    "about this person. Focus on career changes, company moves, and newsworthy events. "
                    "Return your findings in a structured format."
                ),
            ),
            ChatMessage(
                role="user",
                content=f"""
{current_info}

Search Results:
{source_text}

Please analyze these results and identify:
1. Any career updates (new title, new company)
2. Recent news or announcements involving this person
3. Any talks, interviews, or public appearances
4. Any other relevant professional updates

For each finding, indicate:
- Category (career, news, media, other)
- Summary of the finding
- Confidence level (high, medium, low)
- If this suggests updating a CRM field, which field and what value

Respond in a structured way with clear sections for each finding.
""",
            ),
        ]

        try:
            response = await provider.chat(messages)
            findings = self._parse_ai_findings(response.content, sources)
        except Exception:
            # If AI analysis fails, return empty findings
            pass

        return findings

    def _parse_ai_findings(
        self, ai_response: str, sources: list[ResearchSource]
    ) -> list[ResearchFinding]:
        """
        Parse AI response into structured findings.

        This is a simplified parser - in production you might use
        structured output or more sophisticated parsing.
        """
        findings: list[ResearchFinding] = []

        # Simple heuristic parsing
        lines = ai_response.split("\n")
        current_finding: dict | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower_line = line.lower()

            # Detect category headers
            if "career" in lower_line and ("update" in lower_line or ":" in line):
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "career", "text": []}
            elif "news" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "news", "text": []}
            elif ("media" in lower_line or "talk" in lower_line or "interview" in lower_line) and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "media", "text": []}
            elif current_finding is not None:
                current_finding["text"].append(line)

        # Add last finding
        if current_finding:
            findings.append(self._create_finding(current_finding, sources))

        return [f for f in findings if f.summary]

    def _create_finding(
        self, finding_data: dict, sources: list[ResearchSource]
    ) -> ResearchFinding:
        """Create a ResearchFinding from parsed data."""
        text = " ".join(finding_data.get("text", []))

        # Determine confidence based on keywords
        confidence = 0.5
        if "confirm" in text.lower() or "announce" in text.lower():
            confidence = 0.8
        elif "may" in text.lower() or "possibly" in text.lower():
            confidence = 0.3

        # Check for field suggestions
        suggested_field = None
        suggested_value = None

        if finding_data["category"] == "career":
            if "title" in text.lower() or "role" in text.lower():
                suggested_field = "title"
            elif "company" in text.lower() or "join" in text.lower():
                suggested_field = "company"

        return ResearchFinding(
            category=finding_data["category"],
            summary=text[:500] if text else "",
            confidence=confidence,
            sources=sources[:3],  # Link to relevant sources
            suggested_field=suggested_field,
            suggested_value=suggested_value,
        )

    async def _generate_summary(
        self,
        person: Person,
        sources: list[ResearchSource],
        findings: list[ResearchFinding],
        config: ResearchConfig,
    ) -> str:
        """Generate a summary of the research."""
        if not findings:
            return f"No significant updates found for {person.full_name}."

        summary_parts = [f"Research summary for {person.full_name}:"]

        for finding in findings:
            summary_parts.append(f"- [{finding.category}] {finding.summary[:200]}")

        summary_parts.append(f"\nSources reviewed: {len(sources)}")

        return "\n".join(summary_parts)

    async def _create_suggestions(
        self,
        person: Person,
        findings: list[ResearchFinding],
    ) -> None:
        """Create AI suggestions from findings."""
        for finding in findings:
            if finding.suggested_field and finding.suggested_value:
                current_value = getattr(person, finding.suggested_field, None)

                suggestion = AISuggestion(
                    entity_type="person",
                    entity_id=person.id,
                    field_name=finding.suggested_field,
                    current_value=str(current_value) if current_value else None,
                    suggested_value=finding.suggested_value,
                    confidence=finding.confidence,
                    source_url=finding.sources[0].url if finding.sources else None,
                    status=AISuggestionStatus.pending,
                )
                self.db.add(suggestion)

        self.db.flush()
