"""
Search API integrations for AI Research Assistant.

Provides unified interface for web search, YouTube, and podcast search.
"""

from app.services.ai.search.base import (
    BaseSearchClient,
    SearchResult,
    SearchError,
    SearchAuthError,
    SearchRateLimitError,
)
from app.services.ai.search.brave import BraveSearchClient
from app.services.ai.search.youtube import YouTubeSearchClient
from app.services.ai.search.listen_notes import ListenNotesClient
from app.services.ai.search.search_service import SearchService, SearchConfig, get_search_service

__all__ = [
    # Base classes
    "BaseSearchClient",
    "SearchResult",
    "SearchError",
    "SearchAuthError",
    "SearchRateLimitError",
    # Clients
    "BraveSearchClient",
    "YouTubeSearchClient",
    "ListenNotesClient",
    # Service
    "SearchService",
    "SearchConfig",
    "get_search_service",
]
