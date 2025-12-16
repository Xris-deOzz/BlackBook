"""
Listen Notes API client.

Provides search for podcasts and episodes, useful for finding
podcast appearances and interviews by/about contacts.
"""

import httpx
from datetime import datetime

from app.services.ai.search.base import (
    BaseSearchClient,
    SearchResult,
    SearchError,
    SearchAuthError,
    SearchRateLimitError,
)


class ListenNotesClient(BaseSearchClient):
    """
    Listen Notes API client.

    API Documentation: https://www.listennotes.com/api/docs/
    Free tier: 300 requests/month
    """

    BASE_URL = "https://listen-api.listennotes.com/api/v2"

    @property
    def service_name(self) -> str:
        return "listen_notes"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "episode",
        sort_by: str = "relevance",
        published_after: datetime | None = None,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search Listen Notes for podcasts or episodes.

        Args:
            query: Search query
            max_results: Maximum results (1-10 for free tier)
            search_type: "episode" or "podcast"
            sort_by: "relevance" or "date"
            published_after: Only return content published after this date

        Returns:
            List of SearchResult objects
        """
        max_results = min(max_results, 10)  # Free tier limit

        params = {
            "q": query,
            "type": search_type,
            "sort_by_date": 1 if sort_by == "date" else 0,
            "offset": 0,
            "len_min": 0,
            "len_max": 0,  # 0 means no limit
        }

        if published_after:
            params["published_after"] = int(published_after.timestamp() * 1000)

        headers = {
            "X-ListenAPI-Key": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/search",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise SearchAuthError("Invalid Listen Notes API key")
                if response.status_code == 429:
                    raise SearchRateLimitError("Listen Notes API rate limit exceeded")
                if response.status_code != 200:
                    raise SearchError(f"Listen Notes API error: {response.status_code}")

                data = response.json()

                if search_type == "episode":
                    return self._parse_episode_results(data, max_results)
                else:
                    return self._parse_podcast_results(data, max_results)

            except httpx.RequestError as e:
                raise SearchError(f"Listen Notes API request failed: {str(e)}")

    def _parse_episode_results(
        self, data: dict, max_results: int
    ) -> list[SearchResult]:
        """Parse episode search results."""
        results = []

        for item in data.get("results", [])[:max_results]:
            # Parse published date
            published_date = None
            if item.get("pub_date_ms"):
                try:
                    published_date = datetime.fromtimestamp(
                        item["pub_date_ms"] / 1000
                    )
                except (ValueError, TypeError, OSError):
                    pass

            # Duration in minutes
            duration_mins = None
            if item.get("audio_length_sec"):
                duration_mins = item["audio_length_sec"] // 60

            result = SearchResult(
                title=item.get("title_original", ""),
                url=item.get("listennotes_url", ""),
                snippet=self._truncate_snippet(
                    item.get("description_original", "")
                ),
                source="listen_notes",
                published_date=published_date,
                thumbnail_url=item.get("thumbnail"),
                metadata={
                    "podcast_title": item.get("podcast", {}).get(
                        "title_original", ""
                    ),
                    "podcast_id": item.get("podcast", {}).get("id"),
                    "episode_id": item.get("id"),
                    "audio_url": item.get("audio"),
                    "duration_minutes": duration_mins,
                    "explicit": item.get("explicit_content", False),
                },
            )
            results.append(result)

        return results

    def _parse_podcast_results(
        self, data: dict, max_results: int
    ) -> list[SearchResult]:
        """Parse podcast search results."""
        results = []

        for item in data.get("results", [])[:max_results]:
            # Parse latest episode date
            latest_date = None
            if item.get("latest_pub_date_ms"):
                try:
                    latest_date = datetime.fromtimestamp(
                        item["latest_pub_date_ms"] / 1000
                    )
                except (ValueError, TypeError, OSError):
                    pass

            result = SearchResult(
                title=item.get("title_original", ""),
                url=item.get("listennotes_url", ""),
                snippet=self._truncate_snippet(
                    item.get("description_original", "")
                ),
                source="listen_notes",
                published_date=latest_date,
                thumbnail_url=item.get("thumbnail"),
                metadata={
                    "podcast_id": item.get("id"),
                    "publisher": item.get("publisher_original"),
                    "total_episodes": item.get("total_episodes"),
                    "explicit": item.get("explicit_content", False),
                    "genres": [
                        g.get("name") for g in item.get("genre_ids", [])
                        if isinstance(g, dict) and g.get("name")
                    ],
                },
            )
            results.append(result)

        return results

    async def validate_key(self) -> bool:
        """Validate Listen Notes API key."""
        try:
            results = await self.search("test", max_results=1)
            return True
        except SearchAuthError:
            return False
        except Exception:
            return False

    async def get_episode_details(self, episode_id: str) -> SearchResult | None:
        """
        Get detailed information about a specific episode.

        Args:
            episode_id: Listen Notes episode ID

        Returns:
            SearchResult with episode details or None
        """
        headers = {
            "X-ListenAPI-Key": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/episodes/{episode_id}",
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return None

                item = response.json()

                published_date = None
                if item.get("pub_date_ms"):
                    try:
                        published_date = datetime.fromtimestamp(
                            item["pub_date_ms"] / 1000
                        )
                    except (ValueError, TypeError, OSError):
                        pass

                duration_mins = None
                if item.get("audio_length_sec"):
                    duration_mins = item["audio_length_sec"] // 60

                return SearchResult(
                    title=item.get("title", ""),
                    url=item.get("listennotes_url", ""),
                    snippet=self._truncate_snippet(item.get("description", "")),
                    source="listen_notes",
                    published_date=published_date,
                    thumbnail_url=item.get("thumbnail"),
                    metadata={
                        "podcast_title": item.get("podcast", {}).get("title", ""),
                        "podcast_id": item.get("podcast", {}).get("id"),
                        "episode_id": item.get("id"),
                        "audio_url": item.get("audio"),
                        "duration_minutes": duration_mins,
                        "explicit": item.get("explicit_content", False),
                        "transcript": item.get("transcript"),
                    },
                )

            except Exception:
                return None

    async def get_podcast_episodes(
        self,
        podcast_id: str,
        max_results: int = 10,
        sort: str = "recent_first",
    ) -> list[SearchResult]:
        """
        Get episodes from a specific podcast.

        Args:
            podcast_id: Listen Notes podcast ID
            max_results: Maximum results
            sort: "recent_first" or "oldest_first"

        Returns:
            List of SearchResult objects
        """
        headers = {
            "X-ListenAPI-Key": self.api_key,
        }

        params = {
            "sort": sort,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/podcasts/{podcast_id}",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                episodes = data.get("episodes", [])[:max_results]

                results = []
                for item in episodes:
                    published_date = None
                    if item.get("pub_date_ms"):
                        try:
                            published_date = datetime.fromtimestamp(
                                item["pub_date_ms"] / 1000
                            )
                        except (ValueError, TypeError, OSError):
                            pass

                    duration_mins = None
                    if item.get("audio_length_sec"):
                        duration_mins = item["audio_length_sec"] // 60

                    result = SearchResult(
                        title=item.get("title", ""),
                        url=item.get("listennotes_url", ""),
                        snippet=self._truncate_snippet(
                            item.get("description", "")
                        ),
                        source="listen_notes",
                        published_date=published_date,
                        thumbnail_url=item.get("thumbnail"),
                        metadata={
                            "podcast_title": data.get("title", ""),
                            "podcast_id": podcast_id,
                            "episode_id": item.get("id"),
                            "audio_url": item.get("audio"),
                            "duration_minutes": duration_mins,
                        },
                    )
                    results.append(result)

                return results

            except Exception:
                return []
