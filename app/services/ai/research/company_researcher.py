"""
Company/Organization research workflow.

Automated research on organizations, finding news,
funding announcements, and company updates.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Organization, AISuggestion, AISuggestionStatus
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


class CompanyResearcher(ResearchWorkflow):
    """
    Research workflow for organizations/companies.

    Searches for and analyzes:
    - Company news and announcements
    - Funding rounds and financial news
    - Leadership changes
    - Product launches
    - Industry positioning
    """

    async def research(
        self,
        entity_id: UUID,
        config: ResearchConfig | None = None,
    ) -> ResearchResult:
        """
        Execute research on an organization.

        Args:
            entity_id: UUID of the organization to research
            config: Research configuration

        Returns:
            ResearchResult with findings and sources
        """
        config = config or ResearchConfig()
        started_at = datetime.utcnow()

        # Load organization from database
        org = self.db.query(Organization).filter(Organization.id == entity_id).first()
        if not org:
            return ResearchResult(
                entity_type="organization",
                entity_id=entity_id,
                entity_name="Unknown",
                status=ResearchStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                config=config,
                error=f"Organization {entity_id} not found",
            )

        result = ResearchResult(
            entity_type="organization",
            entity_id=entity_id,
            entity_name=org.name,
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
                findings = await self._analyze_findings(org, result.sources, config)
                result.findings = findings

                # Generate summary
                result.summary = await self._generate_summary(
                    org, result.sources, findings, config
                )

                # Create suggestions if configured
                if config.auto_suggest_updates:
                    await self._create_suggestions(org, findings)

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
        Generate search queries for an organization.

        Args:
            entity_id: UUID of the organization
            config: Research configuration

        Returns:
            List of search queries
        """
        org = self.db.query(Organization).filter(Organization.id == entity_id).first()
        if not org:
            return []

        queries = []
        name = org.name

        # Basic company search
        queries.append(f'"{name}"')

        # News and announcements
        queries.append(f'"{name}" news OR announcement')

        # Depth-based additional queries
        if config.depth in [ResearchDepth.STANDARD, ResearchDepth.DEEP]:
            # Category/industry context
            if org.category:
                queries.append(f'"{name}" {org.category}')

            # Funding and financial news
            queries.append(f'"{name}" funding OR investment OR valuation')

        if config.depth == ResearchDepth.DEEP:
            # Leadership and team
            queries.append(f'"{name}" CEO OR leadership OR executive')

            # Product and service news
            queries.append(f'"{name}" product OR launch OR release')

            # Partnerships and deals
            queries.append(f'"{name}" partnership OR acquisition OR deal')

            # Company culture and hiring
            queries.append(f'"{name}" hiring OR culture OR team')

        return queries

    async def _analyze_findings(
        self,
        org: Organization,
        sources: list[ResearchSource],
        config: ResearchConfig,
    ) -> list[ResearchFinding]:
        """
        Use AI to analyze sources and extract findings.

        Args:
            org: Organization being researched
            sources: Sources found during research
            config: Research configuration

        Returns:
            List of findings
        """
        findings: list[ResearchFinding] = []

        # Skip AI analysis if no provider configured
        if not config.provider_name:
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
            for s in sources[:15]
        ])

        # Build prompt for analysis
        current_info = f"""
Current CRM Information:
- Company Name: {org.name}
- Category: {org.category or 'Unknown'}
- Type: {org.org_type.value if org.org_type else 'Unknown'}
- Website: {org.website or 'Unknown'}
- Description: {org.description[:200] if org.description else 'Unknown'}
"""

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a research analyst helping to update a CRM database. "
                    "Analyze the search results and identify any updates or new information "
                    "about this company. Focus on news, funding, leadership changes, and "
                    "significant business developments. Return your findings in a structured format."
                ),
            ),
            ChatMessage(
                role="user",
                content=f"""
{current_info}

Search Results:
{source_text}

Please analyze these results and identify:
1. Recent news or announcements about this company
2. Any funding rounds or financial developments
3. Leadership or team changes
4. Product launches or major updates
5. Industry positioning or competitive developments

For each finding, indicate:
- Category (news, funding, leadership, product, industry)
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
            pass

        return findings

    def _parse_ai_findings(
        self, ai_response: str, sources: list[ResearchSource]
    ) -> list[ResearchFinding]:
        """Parse AI response into structured findings."""
        findings: list[ResearchFinding] = []

        lines = ai_response.split("\n")
        current_finding: dict | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower_line = line.lower()

            # Detect category headers
            if "news" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "news", "text": []}
            elif "funding" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "funding", "text": []}
            elif "leadership" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "leadership", "text": []}
            elif "product" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "product", "text": []}
            elif "industry" in lower_line and ":" in line:
                if current_finding:
                    findings.append(self._create_finding(current_finding, sources))
                current_finding = {"category": "industry", "text": []}
            elif current_finding is not None:
                current_finding["text"].append(line)

        if current_finding:
            findings.append(self._create_finding(current_finding, sources))

        return [f for f in findings if f.summary]

    def _create_finding(
        self, finding_data: dict, sources: list[ResearchSource]
    ) -> ResearchFinding:
        """Create a ResearchFinding from parsed data."""
        text = " ".join(finding_data.get("text", []))

        confidence = 0.5
        if "confirm" in text.lower() or "announce" in text.lower():
            confidence = 0.8
        elif "may" in text.lower() or "rumor" in text.lower():
            confidence = 0.3

        suggested_field = None
        suggested_value = None

        if finding_data["category"] == "funding":
            suggested_field = "notes"
        elif finding_data["category"] == "leadership":
            suggested_field = "notes"

        return ResearchFinding(
            category=finding_data["category"],
            summary=text[:500] if text else "",
            confidence=confidence,
            sources=sources[:3],
            suggested_field=suggested_field,
            suggested_value=suggested_value,
        )

    async def _generate_summary(
        self,
        org: Organization,
        sources: list[ResearchSource],
        findings: list[ResearchFinding],
        config: ResearchConfig,
    ) -> str:
        """Generate a summary of the research."""
        if not findings:
            return f"No significant updates found for {org.name}."

        summary_parts = [f"Research summary for {org.name}:"]

        for finding in findings:
            summary_parts.append(f"- [{finding.category}] {finding.summary[:200]}")

        summary_parts.append(f"\nSources reviewed: {len(sources)}")

        return "\n".join(summary_parts)

    async def _create_suggestions(
        self,
        org: Organization,
        findings: list[ResearchFinding],
    ) -> None:
        """Create AI suggestions from findings."""
        for finding in findings:
            if finding.suggested_field and finding.suggested_value:
                current_value = getattr(org, finding.suggested_field, None)

                suggestion = AISuggestion(
                    entity_type="organization",
                    entity_id=org.id,
                    field_name=finding.suggested_field,
                    current_value=str(current_value) if current_value else None,
                    suggested_value=finding.suggested_value,
                    confidence=finding.confidence,
                    source_url=finding.sources[0].url if finding.sources else None,
                    status=AISuggestionStatus.pending,
                )
                self.db.add(suggestion)

        self.db.flush()
