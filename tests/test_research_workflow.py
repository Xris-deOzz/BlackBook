"""
Tests for research workflows.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.models import Person, Organization, PersonStatus
from app.services.ai.research.workflow import (
    ResearchWorkflow,
    ResearchConfig,
    ResearchResult,
    ResearchStatus,
    ResearchDepth,
    ResearchSource,
    ResearchFinding,
)
from app.services.ai.research.person_researcher import PersonResearcher
from app.services.ai.research.company_researcher import CompanyResearcher


class TestResearchConfig:
    """Test ResearchConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ResearchConfig()

        assert config.depth == ResearchDepth.STANDARD
        assert config.include_news is True
        assert config.include_videos is True
        assert config.include_podcasts is True
        assert config.max_results_per_source == 5
        assert config.auto_suggest_updates is True
        assert config.provider_name is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = ResearchConfig(
            depth=ResearchDepth.DEEP,
            include_news=False,
            max_results_per_source=10,
            provider_name="openai",
        )

        assert config.depth == ResearchDepth.DEEP
        assert config.include_news is False
        assert config.max_results_per_source == 10
        assert config.provider_name == "openai"


class TestResearchSource:
    """Test ResearchSource dataclass."""

    def test_create_source(self):
        """Test creating a research source."""
        source = ResearchSource(
            title="Test Article",
            url="https://example.com/article",
            snippet="This is a test article",
            source_type="web",
        )

        assert source.title == "Test Article"
        assert source.source_type == "web"
        assert source.relevance_score is None

    def test_source_with_date(self):
        """Test source with published date."""
        published = datetime(2024, 1, 15)
        source = ResearchSource(
            title="News",
            url="https://news.example.com",
            snippet="News article",
            source_type="news",
            published_date=published,
        )

        assert source.published_date == published


class TestResearchFinding:
    """Test ResearchFinding dataclass."""

    def test_create_finding(self):
        """Test creating a research finding."""
        finding = ResearchFinding(
            category="career",
            summary="Person got a new job",
            confidence=0.8,
        )

        assert finding.category == "career"
        assert finding.confidence == 0.8
        assert finding.sources == []

    def test_finding_with_suggestion(self):
        """Test finding with field suggestion."""
        finding = ResearchFinding(
            category="career",
            summary="Person is now VP at Company",
            confidence=0.9,
            suggested_field="title",
            suggested_value="Vice President",
        )

        assert finding.suggested_field == "title"
        assert finding.suggested_value == "Vice President"


class TestResearchResult:
    """Test ResearchResult dataclass."""

    def test_create_result(self):
        """Test creating a research result."""
        entity_id = uuid4()
        result = ResearchResult(
            entity_type="person",
            entity_id=entity_id,
            entity_name="John Doe",
            status=ResearchStatus.COMPLETED,
            started_at=datetime(2024, 1, 15, 10, 0),
            completed_at=datetime(2024, 1, 15, 10, 5),
        )

        assert result.entity_type == "person"
        assert result.entity_id == entity_id
        assert result.status == ResearchStatus.COMPLETED

    def test_duration_seconds(self):
        """Test calculating duration."""
        result = ResearchResult(
            entity_type="person",
            entity_id=uuid4(),
            entity_name="Test",
            status=ResearchStatus.COMPLETED,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            completed_at=datetime(2024, 1, 15, 10, 5, 30),
        )

        assert result.duration_seconds == 330.0

    def test_duration_seconds_incomplete(self):
        """Test duration when research not complete."""
        result = ResearchResult(
            entity_type="person",
            entity_id=uuid4(),
            entity_name="Test",
            status=ResearchStatus.IN_PROGRESS,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
        )

        assert result.duration_seconds is None

    def test_to_dict(self):
        """Test converting to dictionary."""
        entity_id = uuid4()
        result = ResearchResult(
            entity_type="person",
            entity_id=entity_id,
            entity_name="John Doe",
            status=ResearchStatus.COMPLETED,
            started_at=datetime(2024, 1, 15, 10, 0),
            completed_at=datetime(2024, 1, 15, 10, 5),
            summary="Research completed successfully",
        )

        data = result.to_dict()

        assert data["entity_type"] == "person"
        assert data["entity_id"] == str(entity_id)
        assert data["entity_name"] == "John Doe"
        assert data["status"] == "completed"
        assert data["summary"] == "Research completed successfully"


class TestPersonResearcher:
    """Test PersonResearcher workflow."""

    @pytest.fixture
    def sample_person(self, db_session):
        """Create a sample person for testing."""
        # Create organization first
        from app.models import Organization, PersonOrganization
        org = Organization(name="Tech Corp", category="Technology")
        db_session.add(org)
        db_session.flush()

        person = Person(
            full_name="Jane Smith",
            title="VP of Engineering",
            linkedin="https://linkedin.com/in/janesmith",
            status=PersonStatus.active,
        )
        db_session.add(person)
        db_session.flush()

        # Create person-organization relationship
        person_org = PersonOrganization(person_id=person.id, organization_id=org.id)
        db_session.add(person_org)
        db_session.flush()
        return person

    @pytest.mark.asyncio
    async def test_research_person_not_found(self, db_session):
        """Test researching non-existent person."""
        researcher = PersonResearcher(db_session)
        result = await researcher.research(uuid4())

        assert result.status == ResearchStatus.FAILED
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_get_search_queries_basic(self, db_session, sample_person):
        """Test generating basic search queries."""
        researcher = PersonResearcher(db_session)
        config = ResearchConfig(depth=ResearchDepth.QUICK)

        queries = await researcher.get_search_queries(sample_person.id, config)

        assert len(queries) >= 1
        assert any("Jane Smith" in q for q in queries)

    @pytest.mark.asyncio
    async def test_get_search_queries_standard(self, db_session, sample_person):
        """Test generating standard depth queries."""
        researcher = PersonResearcher(db_session)
        config = ResearchConfig(depth=ResearchDepth.STANDARD)

        queries = await researcher.get_search_queries(sample_person.id, config)

        # Should include company and title queries
        assert len(queries) >= 2
        assert any("Tech Corp" in q for q in queries)

    @pytest.mark.asyncio
    async def test_get_search_queries_deep(self, db_session, sample_person):
        """Test generating deep search queries."""
        researcher = PersonResearcher(db_session)
        config = ResearchConfig(depth=ResearchDepth.DEEP)

        queries = await researcher.get_search_queries(sample_person.id, config)

        # Should include interview/talk queries
        assert len(queries) >= 4
        assert any("talk" in q.lower() or "interview" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_research_with_mocked_search(self, db_session, sample_person):
        """Test research with mocked search service."""
        researcher = PersonResearcher(db_session)

        # Mock the search service
        with patch.object(researcher, '_search_all_sources', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                ResearchSource(
                    title="Jane Smith joins New Company as CTO",
                    url="https://news.example.com/article",
                    snippet="Jane Smith has been appointed CTO...",
                    source_type="news",
                )
            ]

            # Mock the AI analysis to avoid needing an actual provider
            with patch.object(researcher, '_analyze_findings', new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = []

                with patch.object(researcher, '_generate_summary', new_callable=AsyncMock) as mock_summary:
                    mock_summary.return_value = "Research completed"

                    config = ResearchConfig(auto_suggest_updates=False)
                    result = await researcher.research(sample_person.id, config)

                    assert result.status == ResearchStatus.COMPLETED
                    assert len(result.sources) >= 1


class TestCompanyResearcher:
    """Test CompanyResearcher workflow."""

    @pytest.fixture
    def sample_org(self, db_session):
        """Create a sample organization for testing."""
        org = Organization(
            name="Tech Corp",
            category="Technology",
            description="A technology company with 100-500 employees",
            website="https://techcorp.example.com",
        )
        db_session.add(org)
        db_session.flush()
        return org

    @pytest.mark.asyncio
    async def test_research_org_not_found(self, db_session):
        """Test researching non-existent organization."""
        researcher = CompanyResearcher(db_session)
        result = await researcher.research(uuid4())

        assert result.status == ResearchStatus.FAILED
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_get_search_queries_basic(self, db_session, sample_org):
        """Test generating basic search queries for org."""
        researcher = CompanyResearcher(db_session)
        config = ResearchConfig(depth=ResearchDepth.QUICK)

        queries = await researcher.get_search_queries(sample_org.id, config)

        assert len(queries) >= 2
        assert any("Tech Corp" in q for q in queries)
        assert any("news" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_get_search_queries_deep(self, db_session, sample_org):
        """Test generating deep search queries for org."""
        researcher = CompanyResearcher(db_session)
        config = ResearchConfig(depth=ResearchDepth.DEEP)

        queries = await researcher.get_search_queries(sample_org.id, config)

        # Should include funding, leadership, product queries
        assert len(queries) >= 5
        assert any("funding" in q.lower() for q in queries)
        assert any("leadership" in q.lower() or "ceo" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_research_with_mocked_search(self, db_session, sample_org):
        """Test research with mocked search service."""
        researcher = CompanyResearcher(db_session)

        with patch.object(researcher, '_search_all_sources', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                ResearchSource(
                    title="Tech Corp raises $50M Series B",
                    url="https://news.example.com/funding",
                    snippet="Tech Corp announced today...",
                    source_type="news",
                )
            ]

            with patch.object(researcher, '_analyze_findings', new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = []

                with patch.object(researcher, '_generate_summary', new_callable=AsyncMock) as mock_summary:
                    mock_summary.return_value = "Research completed"

                    config = ResearchConfig(auto_suggest_updates=False)
                    result = await researcher.research(sample_org.id, config)

                    assert result.status == ResearchStatus.COMPLETED
                    assert result.entity_name == "Tech Corp"
