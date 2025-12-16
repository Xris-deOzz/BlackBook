"""
YouTube Data API client.

Provides search for YouTube videos, useful for finding talks, interviews,
and presentations by/about contacts.
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


class YouTubeSearchClient(BaseSearchClient):
    """
    YouTube Data API v3 client.

    API Documentation: https://developers.google.com/youtube/v3/docs/search/list
    Free tier: 10,000 quota units/day (~100 searches/day)
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    @property
    def service_name(self) -> str:
        return "youtube"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        video_type: str = "video",
        order: str = "relevance",
        published_after: datetime | None = None,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search YouTube videos.

        Args:
            query: Search query
            max_results: Maximum results (1-50)
            video_type: Type filter (video, channel, playlist)
            order: Sort order (relevance, date, rating, viewCount)
            published_after: Only return videos published after this date

        Returns:
            List of SearchResult objects
        """
        max_results = min(max_results, 50)  # API limit

        params = {
            "part": "snippet",
            "q": query,
            "type": video_type,
            "maxResults": max_results,
            "order": order,
            "key": self.api_key,
        }

        if published_after:
            params["publishedAfter"] = published_after.isoformat() + "Z"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/search",
                    params=params,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise SearchAuthError("Invalid YouTube API key")
                if response.status_code == 403:
                    error_data = response.json()
                    if "quotaExceeded" in str(error_data):
                        raise SearchRateLimitError("YouTube API quota exceeded")
                    raise SearchAuthError("YouTube API access denied")
                if response.status_code != 200:
                    raise SearchError(f"YouTube API error: {response.status_code}")

                data = response.json()
                return self._parse_results(data)

            except httpx.RequestError as e:
                raise SearchError(f"YouTube API request failed: {str(e)}")

    def _parse_results(self, data: dict) -> list[SearchResult]:
        """Parse YouTube API search response."""
        results = []

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")

            if not video_id:
                # Handle channel or playlist results
                if item.get("id", {}).get("channelId"):
                    video_id = item["id"]["channelId"]
                    url = f"https://www.youtube.com/channel/{video_id}"
                elif item.get("id", {}).get("playlistId"):
                    video_id = item["id"]["playlistId"]
                    url = f"https://www.youtube.com/playlist?list={video_id}"
                else:
                    continue
            else:
                url = f"https://www.youtube.com/watch?v={video_id}"

            # Parse published date
            published_date = None
            if snippet.get("publishedAt"):
                try:
                    published_date = datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            # Get best thumbnail
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("high", {}).get("url") or
                thumbnails.get("medium", {}).get("url") or
                thumbnails.get("default", {}).get("url")
            )

            result = SearchResult(
                title=snippet.get("title", ""),
                url=url,
                snippet=self._truncate_snippet(snippet.get("description", "")),
                source="youtube",
                published_date=published_date,
                thumbnail_url=thumbnail_url,
                metadata={
                    "channel_title": snippet.get("channelTitle"),
                    "channel_id": snippet.get("channelId"),
                    "video_id": video_id,
                },
            )
            results.append(result)

        return results

    async def validate_key(self) -> bool:
        """Validate YouTube API key."""
        try:
            # Do a minimal search to test the key
            results = await self.search("test", max_results=1)
            return True
        except SearchAuthError:
            return False
        except Exception:
            return False

    async def get_video_details(self, video_id: str) -> SearchResult | None:
        """
        Get detailed information about a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            SearchResult with video details or None
        """
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/videos",
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                items = data.get("items", [])

                if not items:
                    return None

                item = items[0]
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})

                published_date = None
                if snippet.get("publishedAt"):
                    try:
                        published_date = datetime.fromisoformat(
                            snippet["publishedAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("high", {}).get("url") or
                    thumbnails.get("medium", {}).get("url")
                )

                return SearchResult(
                    title=snippet.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    snippet=self._truncate_snippet(snippet.get("description", "")),
                    source="youtube",
                    published_date=published_date,
                    thumbnail_url=thumbnail_url,
                    metadata={
                        "channel_title": snippet.get("channelTitle"),
                        "channel_id": snippet.get("channelId"),
                        "video_id": video_id,
                        "view_count": int(statistics.get("viewCount", 0)),
                        "like_count": int(statistics.get("likeCount", 0)),
                        "comment_count": int(statistics.get("commentCount", 0)),
                        "duration": item.get("contentDetails", {}).get("duration"),
                    },
                )

            except Exception:
                return None

    async def search_channel_videos(
        self,
        channel_id: str,
        max_results: int = 10,
        order: str = "date",
    ) -> list[SearchResult]:
        """
        Search videos from a specific channel.

        Args:
            channel_id: YouTube channel ID
            max_results: Maximum results
            order: Sort order

        Returns:
            List of SearchResult objects
        """
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": order,
            "key": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/search",
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                return self._parse_results(data)

            except Exception:
                return []
