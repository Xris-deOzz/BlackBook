"""
Unified search service.

Aggregates results from multiple search providers and provides
a consistent interface for the AI research workflow.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AIAPIKey, AIProvider, AIProviderType
from app.services.ai.search.base import (
    BaseSearchClient,
    SearchResult,
    SearchError,
    SearchAuthError,
)
from app.services.ai.search.brave import BraveSearchClient
from app.services.ai.search.youtube import YouTubeSearchClient
from app.services.ai.search.listen_notes import ListenNotesClient


@dataclass
class SearchConfig:
    """Configuration for a search operation."""

    query: str
    sources: list[str] | None = None  # None means all available
    max_results_per_source: int = 5
    published_after: datetime | None = None
    include_news: bool = False


@dataclass
class AggregatedSearchResults:
    """Results from multiple search sources."""

    query: str
    results: list[SearchResult]
    sources_searched: list[str]
    sources_failed: dict[str, str]  # source -> error message
    total_results: int

    def by_source(self, source: str) -> list[SearchResult]:
        """Get results from a specific source."""
        return [r for r in self.results if r.source == source]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                    "published_date": (
                        r.published_date.isoformat() if r.published_date else None
                    ),
                    "thumbnail_url": r.thumbnail_url,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
            "sources_searched": self.sources_searched,
            "sources_failed": self.sources_failed,
            "total_results": self.total_results,
        }


class SearchService:
    """
    Unified search service that aggregates results from multiple providers.

    Supported sources:
    - brave: Web search via Brave Search API
    - youtube: Video search via YouTube Data API
    - listen_notes: Podcast search via Listen Notes API
    """

    SUPPORTED_SOURCES = ["brave", "youtube", "listen_notes"]

    def __init__(self, db: Session):
        self.db = db
        self._clients: dict[str, BaseSearchClient] = {}

    def _get_api_key(self, service_name: str) -> str | None:
        """Get API key for a service from database."""
        # Map service names to provider types (enum values)
        provider_type_map = {
            "brave": AIProviderType.brave_search,
            "youtube": AIProviderType.youtube,
            "listen_notes": AIProviderType.listen_notes,
        }

        provider_type = provider_type_map.get(service_name)
        if not provider_type:
            return None

        # Query for API key by api_type enum (not by name)
        provider = (
            self.db.query(AIProvider)
            .filter(AIProvider.api_type == provider_type)
            .filter(AIProvider.is_active.is_(True))
            .first()
        )

        if provider:
            # Get API key - accept keys that are valid (True) or not yet tested (None)
            # Only reject keys explicitly marked invalid (False)
            api_key = (
                self.db.query(AIAPIKey)
                .filter(AIAPIKey.provider_id == provider.id)
                .filter(AIAPIKey.is_valid.is_not(False))
                .first()
            )
            if api_key:
                return api_key.get_api_key()

        return None

    def _get_client(self, source: str) -> BaseSearchClient | None:
        """Get or create a search client for the specified source."""
        if source in self._clients:
            return self._clients[source]

        api_key = self._get_api_key(source)
        if not api_key:
            return None

        client: BaseSearchClient | None = None

        if source == "brave":
            client = BraveSearchClient(api_key)
        elif source == "youtube":
            client = YouTubeSearchClient(api_key)
        elif source == "listen_notes":
            client = ListenNotesClient(api_key)

        if client:
            self._clients[source] = client

        return client

    def get_available_sources(self) -> list[str]:
        """Get list of sources with valid API keys."""
        available = []
        for source in self.SUPPORTED_SOURCES:
            if self._get_api_key(source):
                available.append(source)
        return available

    async def search(self, config: SearchConfig) -> AggregatedSearchResults:
        """
        Execute search across multiple sources.

        Args:
            config: Search configuration

        Returns:
            AggregatedSearchResults with results from all sources
        """
        # Determine which sources to search
        sources = config.sources or self.SUPPORTED_SOURCES
        sources = [s for s in sources if s in self.SUPPORTED_SOURCES]

        # Create tasks for each source
        tasks = []
        source_names = []

        for source in sources:
            client = self._get_client(source)
            if client:
                task = self._search_source(
                    client=client,
                    source=source,
                    query=config.query,
                    max_results=config.max_results_per_source,
                    published_after=config.published_after,
                    include_news=config.include_news,
                )
                tasks.append(task)
                source_names.append(source)

        # Execute all searches concurrently
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_results: list[SearchResult] = []
        sources_searched: list[str] = []
        sources_failed: dict[str, str] = {}

        for source, result in zip(source_names, results_list):
            if isinstance(result, Exception):
                sources_failed[source] = str(result)
            elif isinstance(result, list):
                all_results.extend(result)
                sources_searched.append(source)

        return AggregatedSearchResults(
            query=config.query,
            results=all_results,
            sources_searched=sources_searched,
            sources_failed=sources_failed,
            total_results=len(all_results),
        )

    async def _search_source(
        self,
        client: BaseSearchClient,
        source: str,
        query: str,
        max_results: int,
        published_after: datetime | None,
        include_news: bool,
    ) -> list[SearchResult]:
        """Execute search for a single source."""
        results: list[SearchResult] = []

        if source == "brave":
            # Web search
            brave_client = client
            results = await brave_client.search(
                query=query,
                max_results=max_results,
            )

            # Optionally add news results
            if include_news:
                news_results = await brave_client.search_news(
                    query=query,
                    max_results=max_results,
                )
                results.extend(news_results)

        elif source == "youtube":
            results = await client.search(
                query=query,
                max_results=max_results,
                published_after=published_after,
            )

        elif source == "listen_notes":
            results = await client.search(
                query=query,
                max_results=max_results,
                search_type="episode",
                published_after=published_after,
            )

        return results

    async def search_person(
        self,
        name: str,
        company: str | None = None,
        title: str | None = None,
        max_results_per_source: int = 5,
    ) -> AggregatedSearchResults:
        """
        Search for information about a person.

        Constructs appropriate queries for different sources.

        Args:
            name: Person's full name
            company: Optional company name for context
            title: Optional job title for context
            max_results_per_source: Maximum results per source

        Returns:
            AggregatedSearchResults
        """
        # Build search query
        query_parts = [f'"{name}"']  # Exact name match
        if company:
            query_parts.append(company)
        if title:
            query_parts.append(title)

        query = " ".join(query_parts)

        config = SearchConfig(
            query=query,
            max_results_per_source=max_results_per_source,
            include_news=True,
        )

        return await self.search(config)

    async def search_company(
        self,
        company_name: str,
        include_news: bool = True,
        max_results_per_source: int = 5,
    ) -> AggregatedSearchResults:
        """
        Search for information about a company.

        Args:
            company_name: Company name
            include_news: Include news results
            max_results_per_source: Maximum results per source

        Returns:
            AggregatedSearchResults
        """
        config = SearchConfig(
            query=f'"{company_name}"',
            sources=["brave"],  # Company search mainly uses web
            max_results_per_source=max_results_per_source,
            include_news=include_news,
        )

        return await self.search(config)

    async def find_interviews(
        self,
        person_name: str,
        max_results: int = 10,
    ) -> AggregatedSearchResults:
        """
        Find interviews and podcast appearances for a person.

        Args:
            person_name: Person's name
            max_results: Maximum results per source

        Returns:
            AggregatedSearchResults from YouTube and Listen Notes
        """
        config = SearchConfig(
            query=f'"{person_name}" interview',
            sources=["youtube", "listen_notes"],
            max_results_per_source=max_results,
        )

        return await self.search(config)

    async def find_talks(
        self,
        person_name: str,
        max_results: int = 10,
    ) -> AggregatedSearchResults:
        """
        Find conference talks and presentations by a person.

        Args:
            person_name: Person's name
            max_results: Maximum results per source

        Returns:
            AggregatedSearchResults from YouTube
        """
        config = SearchConfig(
            query=f'"{person_name}" talk OR presentation OR keynote',
            sources=["youtube"],
            max_results_per_source=max_results,
        )

        return await self.search(config)


def get_search_service(db: Session) -> SearchService:
    """Factory function to create SearchService."""
    return SearchService(db)
