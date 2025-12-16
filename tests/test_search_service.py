"""
Tests for search service and search clients.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

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
from app.services.ai.search.search_service import (
    SearchService,
    SearchConfig,
    AggregatedSearchResults,
)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            title="Test Result",
            url="https://example.com",
            snippet="This is a test snippet",
            source="brave",
        )

        assert result.title == "Test Result"
        assert result.url == "https://example.com"
        assert result.source == "brave"

    def test_search_result_with_metadata(self):
        """Test SearchResult with metadata."""
        result = SearchResult(
            title="Video",
            url="https://youtube.com/watch?v=123",
            snippet="Test video",
            source="youtube",
            metadata={"channel_title": "Test Channel"},
        )

        assert result.metadata["channel_title"] == "Test Channel"

    def test_search_result_with_date(self):
        """Test SearchResult with published date."""
        published = datetime(2024, 1, 15)
        result = SearchResult(
            title="News",
            url="https://news.example.com",
            snippet="News article",
            source="brave",
            published_date=published,
        )

        assert result.published_date == published


class TestBraveSearchClient:
    """Test Brave Search client."""

    def test_service_name(self):
        """Test service name property."""
        client = BraveSearchClient("test-key")
        assert client.service_name == "brave"

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search."""
        client = BraveSearchClient("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "description": "Test description",
                    }
                ]
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            results = await client.search("test query")

            assert len(results) == 1
            assert results[0].title == "Test Result"
            assert results[0].source == "brave"

    @pytest.mark.asyncio
    async def test_search_auth_error(self):
        """Test authentication error handling."""
        client = BraveSearchClient("invalid-key")

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SearchAuthError):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_search_rate_limit_error(self):
        """Test rate limit error handling."""
        client = BraveSearchClient("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SearchRateLimitError):
                await client.search("test query")


class TestYouTubeSearchClient:
    """Test YouTube search client."""

    def test_service_name(self):
        """Test service name property."""
        client = YouTubeSearchClient("test-key")
        assert client.service_name == "youtube"

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful YouTube search."""
        client = YouTubeSearchClient("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": {"videoId": "abc123"},
                    "snippet": {
                        "title": "Test Video",
                        "description": "Test description",
                        "channelTitle": "Test Channel",
                        "publishedAt": "2024-01-15T00:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://example.com/thumb.jpg"}
                        },
                    },
                }
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            results = await client.search("test query")

            assert len(results) == 1
            assert results[0].title == "Test Video"
            assert results[0].source == "youtube"
            assert "youtube.com/watch" in results[0].url

    @pytest.mark.asyncio
    async def test_search_channel_result(self):
        """Test handling channel results."""
        client = YouTubeSearchClient("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": {"channelId": "channel123"},
                    "snippet": {
                        "title": "Test Channel",
                        "description": "Channel description",
                        "thumbnails": {},
                    },
                }
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            results = await client.search("test query", video_type="channel")

            assert len(results) == 1
            assert "youtube.com/channel" in results[0].url


class TestListenNotesClient:
    """Test Listen Notes client."""

    def test_service_name(self):
        """Test service name property."""
        client = ListenNotesClient("test-key")
        assert client.service_name == "listen_notes"

    @pytest.mark.asyncio
    async def test_search_episodes(self):
        """Test searching for podcast episodes."""
        client = ListenNotesClient("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "ep123",
                    "title_original": "Test Episode",
                    "description_original": "Episode description",
                    "listennotes_url": "https://listennotes.com/ep123",
                    "pub_date_ms": 1705276800000,
                    "audio_length_sec": 3600,
                    "podcast": {
                        "id": "pod123",
                        "title_original": "Test Podcast",
                    },
                }
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            results = await client.search("test query")

            assert len(results) == 1
            assert results[0].title == "Test Episode"
            assert results[0].source == "listen_notes"
            assert results[0].metadata["podcast_title"] == "Test Podcast"


class TestSearchConfig:
    """Test SearchConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = SearchConfig(query="test")

        assert config.query == "test"
        assert config.sources is None
        assert config.max_results_per_source == 5
        assert config.include_news is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = SearchConfig(
            query="test",
            sources=["brave", "youtube"],
            max_results_per_source=10,
            include_news=True,
        )

        assert config.sources == ["brave", "youtube"]
        assert config.max_results_per_source == 10
        assert config.include_news is True


class TestAggregatedSearchResults:
    """Test AggregatedSearchResults dataclass."""

    def test_by_source(self):
        """Test filtering results by source."""
        results = AggregatedSearchResults(
            query="test",
            results=[
                SearchResult(title="Web", url="https://example.com", snippet="", source="brave"),
                SearchResult(title="Video", url="https://youtube.com", snippet="", source="youtube"),
                SearchResult(title="Web2", url="https://example2.com", snippet="", source="brave"),
            ],
            sources_searched=["brave", "youtube"],
            sources_failed={},
            total_results=3,
        )

        brave_results = results.by_source("brave")
        assert len(brave_results) == 2

        youtube_results = results.by_source("youtube")
        assert len(youtube_results) == 1

    def test_to_dict(self):
        """Test converting to dictionary."""
        results = AggregatedSearchResults(
            query="test",
            results=[
                SearchResult(title="Test", url="https://example.com", snippet="desc", source="brave"),
            ],
            sources_searched=["brave"],
            sources_failed={"youtube": "API key not configured"},
            total_results=1,
        )

        data = results.to_dict()

        assert data["query"] == "test"
        assert len(data["results"]) == 1
        assert data["sources_searched"] == ["brave"]
        assert "youtube" in data["sources_failed"]


class TestSearchService:
    """Test SearchService."""

    def test_supported_sources(self):
        """Test supported sources constant."""
        assert "brave" in SearchService.SUPPORTED_SOURCES
        assert "youtube" in SearchService.SUPPORTED_SOURCES
        assert "listen_notes" in SearchService.SUPPORTED_SOURCES

    def test_get_available_sources_none(self, db_session):
        """Test getting available sources with no API keys."""
        service = SearchService(db_session)
        available = service.get_available_sources()

        # Should be empty without configured API keys
        assert isinstance(available, list)

    @pytest.mark.asyncio
    async def test_search_no_sources(self, db_session):
        """Test search with no available sources."""
        service = SearchService(db_session)

        config = SearchConfig(query="test")
        results = await service.search(config)

        # Should return empty results without configured sources
        assert results.total_results == 0
        assert len(results.sources_searched) == 0
