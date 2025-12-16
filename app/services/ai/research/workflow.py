"""
Base research workflow infrastructure.

Defines the core workflow patterns and configuration for
AI-powered research operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.ai.search import SearchService, SearchResult
from app.services.ai.tools import ToolRegistry, ToolExecutor, get_default_tools


class ResearchStatus(str, Enum):
    """Status of a research operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchDepth(str, Enum):
    """Depth of research to perform."""

    QUICK = "quick"  # Basic search, minimal analysis
    STANDARD = "standard"  # Multiple searches, moderate analysis
    DEEP = "deep"  # Comprehensive search, detailed analysis


@dataclass
class ResearchConfig:
    """Configuration for a research operation."""

    depth: ResearchDepth = ResearchDepth.STANDARD
    include_news: bool = True
    include_videos: bool = True
    include_podcasts: bool = True
    max_results_per_source: int = 5
    auto_suggest_updates: bool = True
    provider_name: str | None = None  # AI provider to use


@dataclass
class ResearchSource:
    """A source found during research."""

    title: str
    url: str
    snippet: str
    source_type: str  # "web", "news", "video", "podcast"
    published_date: datetime | None = None
    relevance_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_search_result(
        cls, result: SearchResult, source_type: str
    ) -> "ResearchSource":
        """Create from a SearchResult."""
        return cls(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            source_type=source_type,
            published_date=result.published_date,
            metadata=result.metadata,
        )


@dataclass
class ResearchFinding:
    """A finding or insight from research."""

    category: str  # "career", "company", "news", "social", etc.
    summary: str
    confidence: float  # 0.0 to 1.0
    sources: list[ResearchSource] = field(default_factory=list)
    suggested_field: str | None = None  # CRM field this applies to
    suggested_value: str | None = None  # Suggested value for the field


@dataclass
class ResearchResult:
    """Complete result of a research operation."""

    entity_type: str  # "person" or "organization"
    entity_id: UUID
    entity_name: str
    status: ResearchStatus
    started_at: datetime
    completed_at: datetime | None = None
    config: ResearchConfig = field(default_factory=ResearchConfig)
    sources: list[ResearchSource] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    summary: str | None = None
    error: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Duration of the research operation in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "entity_name": self.entity_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "config": {
                "depth": self.config.depth.value,
                "include_news": self.config.include_news,
                "include_videos": self.config.include_videos,
                "include_podcasts": self.config.include_podcasts,
            },
            "sources": [
                {
                    "title": s.title,
                    "url": s.url,
                    "snippet": s.snippet,
                    "source_type": s.source_type,
                    "published_date": (
                        s.published_date.isoformat() if s.published_date else None
                    ),
                }
                for s in self.sources
            ],
            "findings": [
                {
                    "category": f.category,
                    "summary": f.summary,
                    "confidence": f.confidence,
                    "suggested_field": f.suggested_field,
                    "suggested_value": f.suggested_value,
                }
                for f in self.findings
            ],
            "summary": self.summary,
            "error": self.error,
        }


class ResearchWorkflow(ABC):
    """
    Abstract base class for research workflows.

    Defines the common interface and infrastructure for all
    research operations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.search_service = SearchService(db)
        self._tool_registry: ToolRegistry | None = None
        self._tool_executor: ToolExecutor | None = None

    @property
    def tool_registry(self) -> ToolRegistry:
        """Get the tool registry, creating if needed."""
        if self._tool_registry is None:
            self._tool_registry = ToolRegistry()
            for tool in get_default_tools():
                self._tool_registry.register(tool)
        return self._tool_registry

    @property
    def tool_executor(self) -> ToolExecutor:
        """Get the tool executor, creating if needed."""
        if self._tool_executor is None:
            self._tool_executor = ToolExecutor(self.tool_registry, self.db)
        return self._tool_executor

    @abstractmethod
    async def research(
        self,
        entity_id: UUID,
        config: ResearchConfig | None = None,
    ) -> ResearchResult:
        """
        Execute research on an entity.

        Args:
            entity_id: UUID of the entity to research
            config: Research configuration

        Returns:
            ResearchResult with findings and sources
        """
        pass

    @abstractmethod
    async def get_search_queries(
        self,
        entity_id: UUID,
        config: ResearchConfig,
    ) -> list[str]:
        """
        Generate search queries for an entity.

        Args:
            entity_id: UUID of the entity
            config: Research configuration

        Returns:
            List of search queries to execute
        """
        pass

    async def _search_all_sources(
        self,
        query: str,
        config: ResearchConfig,
    ) -> list[ResearchSource]:
        """
        Execute searches across all configured sources.

        Args:
            query: Search query
            config: Research configuration

        Returns:
            List of ResearchSource objects
        """
        from app.services.ai.search import SearchConfig

        sources: list[ResearchSource] = []

        # Determine which sources to search
        search_sources = ["brave"]
        if config.include_videos:
            search_sources.append("youtube")
        if config.include_podcasts:
            search_sources.append("listen_notes")

        # Execute search
        search_config = SearchConfig(
            query=query,
            sources=search_sources,
            max_results_per_source=config.max_results_per_source,
            include_news=config.include_news,
        )
        results = await self.search_service.search(search_config)

        # Convert to ResearchSource objects
        for result in results.results:
            source_type = "web"
            if result.source == "youtube":
                source_type = "video"
            elif result.source == "listen_notes":
                source_type = "podcast"
            elif config.include_news and "news" in result.metadata.get("type", ""):
                source_type = "news"

            sources.append(ResearchSource.from_search_result(result, source_type))

        return sources

    def _deduplicate_sources(
        self, sources: list[ResearchSource]
    ) -> list[ResearchSource]:
        """Remove duplicate sources based on URL."""
        seen_urls: set[str] = set()
        unique: list[ResearchSource] = []

        for source in sources:
            if source.url not in seen_urls:
                seen_urls.add(source.url)
                unique.append(source)

        return unique
