"""
Brave Search API client.

Brave Search provides privacy-focused web search with a generous free tier
(2,000 searches/month).
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


class BraveSearchClient(BaseSearchClient):
    """
    Brave Search API client.

    API Documentation: https://api.search.brave.com/app/documentation/web-search
    """

    BASE_URL = "https://api.search.brave.com/res/v1"

    @property
    def service_name(self) -> str:
        return "brave"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        country: str = "us",
        search_lang: str = "en",
        freshness: str | None = None,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search the web using Brave Search.

        Args:
            query: Search query
            max_results: Maximum results (1-20)
            country: Country code for results
            search_lang: Language for results
            freshness: Filter by freshness (pd=past day, pw=past week, pm=past month, py=past year)

        Returns:
            List of SearchResult objects
        """
        max_results = min(max_results, 20)  # API limit

        params = {
            "q": query,
            "count": max_results,
            "country": country,
            "search_lang": search_lang,
            "text_decorations": False,
        }

        if freshness:
            params["freshness"] = freshness

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/web/search",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise SearchAuthError("Invalid Brave Search API key")
                if response.status_code == 429:
                    raise SearchRateLimitError("Brave Search rate limit exceeded")
                if response.status_code != 200:
                    raise SearchError(f"Brave Search error: {response.status_code}")

                data = response.json()
                return self._parse_results(data)

            except httpx.RequestError as e:
                raise SearchError(f"Brave Search request failed: {str(e)}")

    def _parse_results(self, data: dict) -> list[SearchResult]:
        """Parse Brave Search API response."""
        results = []

        web_results = data.get("web", {}).get("results", [])

        for item in web_results:
            # Parse published date if available
            published_date = None
            if item.get("page_age"):
                try:
                    published_date = datetime.fromisoformat(
                        item["page_age"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=self._truncate_snippet(item.get("description", "")),
                source="brave",
                published_date=published_date,
                thumbnail_url=item.get("thumbnail", {}).get("src"),
                metadata={
                    "language": item.get("language"),
                    "family_friendly": item.get("family_friendly"),
                },
            )
            results.append(result)

        return results

    async def validate_key(self) -> bool:
        """Validate Brave Search API key."""
        try:
            # Do a minimal search to test the key
            results = await self.search("test", max_results=1)
            return True
        except SearchAuthError:
            return False
        except Exception:
            return False

    async def search_news(
        self,
        query: str,
        max_results: int = 10,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search news specifically.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of SearchResult objects
        """
        params = {
            "q": query,
            "count": min(max_results, 20),
        }

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/news/search",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise SearchAuthError("Invalid Brave Search API key")
                if response.status_code == 429:
                    raise SearchRateLimitError("Brave Search rate limit exceeded")
                if response.status_code != 200:
                    raise SearchError(f"Brave Search news error: {response.status_code}")

                data = response.json()
                return self._parse_news_results(data)

            except httpx.RequestError as e:
                raise SearchError(f"Brave Search request failed: {str(e)}")

    def _parse_news_results(self, data: dict) -> list[SearchResult]:
        """Parse Brave News API response."""
        results = []

        news_results = data.get("results", [])

        for item in news_results:
            published_date = None
            if item.get("age"):
                try:
                    published_date = datetime.fromisoformat(
                        item["age"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=self._truncate_snippet(item.get("description", "")),
                source="brave_news",
                published_date=published_date,
                thumbnail_url=item.get("thumbnail", {}).get("src"),
                metadata={
                    "source_name": item.get("meta_url", {}).get("hostname"),
                },
            )
            results.append(result)

        return results
