"""
Base classes for search API clients.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class SearchError(Exception):
    """Base exception for search errors."""
    pass


class SearchAuthError(SearchError):
    """Authentication error with search API."""
    pass


class SearchRateLimitError(SearchError):
    """Rate limit exceeded for search API."""
    pass


@dataclass
class SearchResult:
    """
    Unified search result format.

    Attributes:
        title: Result title
        url: Source URL
        snippet: Description or excerpt
        source: Source service (brave, youtube, listen_notes)
        published_date: When content was published (if available)
        thumbnail_url: Thumbnail image URL (if available)
        metadata: Additional source-specific data
    """
    title: str
    url: str
    snippet: str
    source: str
    published_date: datetime | None = None
    thumbnail_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "thumbnail_url": self.thumbnail_url,
            "metadata": self.metadata,
        }

    def to_context_string(self) -> str:
        """Convert to string for AI context."""
        parts = [f"**{self.title}**"]
        if self.snippet:
            parts.append(self.snippet)
        parts.append(f"Source: {self.url}")
        return "\n".join(parts)


class BaseSearchClient(ABC):
    """
    Abstract base class for search API clients.

    All search clients must implement these methods to provide
    a unified interface for the AI research assistant.
    """

    def __init__(self, api_key: str):
        """
        Initialize search client.

        Args:
            api_key: API key for the service
        """
        self.api_key = api_key

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of this search service."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search for content.

        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Service-specific parameters

        Returns:
            List of SearchResult objects

        Raises:
            SearchError: If search fails
            SearchAuthError: If authentication fails
            SearchRateLimitError: If rate limited
        """
        pass

    @abstractmethod
    async def validate_key(self) -> bool:
        """
        Validate the API key.

        Returns:
            True if key is valid, False otherwise
        """
        pass

    def _truncate_snippet(self, text: str, max_length: int = 500) -> str:
        """
        Truncate snippet to reasonable length.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length].rsplit(" ", 1)[0] + "..."
