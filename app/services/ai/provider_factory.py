"""
Provider factory for creating AI provider instances.

Handles provider instantiation, API key retrieval from database,
and caching of provider instances.
"""

from functools import lru_cache
from typing import Type
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.ai.base_provider import BaseProvider, ProviderError


# Provider registry
_PROVIDERS: dict[str, Type[BaseProvider]] = {}


def register_provider(api_type: str, provider_class: Type[BaseProvider]):
    """Register a provider class for an API type."""
    _PROVIDERS[api_type] = provider_class


# Register built-in providers
def _register_builtin_providers():
    """Register all built-in providers."""
    from app.services.ai.openai_provider import OpenAIProvider
    from app.services.ai.anthropic_provider import AnthropicProvider
    from app.services.ai.google_provider import GoogleProvider

    register_provider("openai", OpenAIProvider)
    register_provider("anthropic", AnthropicProvider)
    register_provider("google", GoogleProvider)


# Call on module import
_register_builtin_providers()


class ProviderFactory:
    """
    Factory for creating AI provider instances.

    Handles:
    - Loading API keys from database (encrypted)
    - Creating provider instances with proper configuration
    - Caching provider instances for reuse
    """

    def __init__(self, db: Session):
        """
        Initialize the factory.

        Args:
            db: Database session for loading API keys
        """
        self.db = db
        self._cache: dict[str, BaseProvider] = {}

    def get_provider(
        self,
        provider_name: str,
        api_key: str | None = None,
    ) -> BaseProvider:
        """
        Get a provider instance.

        Args:
            provider_name: Provider name (e.g., "openai", "anthropic")
            api_key: Optional API key (if not provided, loads from DB)

        Returns:
            Provider instance

        Raises:
            ProviderError: If provider not found or no valid API key
        """
        # Check if provider type is registered
        if provider_name not in _PROVIDERS:
            raise ProviderError(
                f"Unknown provider: {provider_name}. Available: {list(_PROVIDERS.keys())}",
                provider=provider_name,
            )

        # Use provided key or load from database
        if api_key is None:
            api_key = self._load_api_key(provider_name)

        if not api_key:
            raise ProviderError(
                f"No API key configured for {provider_name}",
                provider=provider_name,
            )

        # Check cache
        cache_key = f"{provider_name}:{api_key[:8]}"  # Use first 8 chars as cache key
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Create new provider instance
        provider_class = _PROVIDERS[provider_name]
        provider = provider_class(api_key=api_key)

        # Cache for reuse
        self._cache[cache_key] = provider

        return provider

    def get_provider_by_type(self, api_type: str) -> BaseProvider:
        """
        Get a provider by API type.

        Args:
            api_type: API type (e.g., "openai", "anthropic", "google")

        Returns:
            Provider instance
        """
        return self.get_provider(api_type)

    def _load_api_key(self, provider_name: str) -> str | None:
        """
        Load API key from database.

        Args:
            provider_name: Provider name to load key for

        Returns:
            Decrypted API key or None if not found
        """
        from app.models import AIProvider, AIAPIKey, AIProviderType

        # Convert string to enum for comparison
        try:
            api_type_enum = AIProviderType(provider_name)
        except ValueError:
            return None

        # Find the provider
        provider = (
            self.db.query(AIProvider)
            .filter(AIProvider.api_type == api_type_enum)
            .filter(AIProvider.is_active == True)
            .first()
        )

        if not provider:
            return None

        # Find a valid API key for this provider
        api_key = (
            self.db.query(AIAPIKey)
            .filter(AIAPIKey.provider_id == provider.id)
            .filter(AIAPIKey.is_valid != False)  # Include NULL (not tested) and True
            .first()
        )

        if not api_key:
            return None

        # Decrypt and return
        return api_key.get_api_key()

    def get_available_providers(self) -> list[dict]:
        """
        Get list of available providers with valid API keys.

        Returns:
            List of dicts with provider info:
            - name: Display name
            - api_type: Provider type
            - models: Available models
        """
        from app.models import AIProvider, AIAPIKey

        result = []

        # Query all active providers with valid keys
        providers = (
            self.db.query(AIProvider)
            .filter(AIProvider.is_active == True)
            .all()
        )

        for provider in providers:
            # Check if provider has a valid API key
            has_key = (
                self.db.query(AIAPIKey)
                .filter(AIAPIKey.provider_id == provider.id)
                .filter(AIAPIKey.is_valid != False)
                .first()
            ) is not None

            if has_key and provider.api_type.value in _PROVIDERS:
                provider_class = _PROVIDERS[provider.api_type.value]
                result.append({
                    "name": provider.name,
                    "api_type": provider.api_type.value,
                    "models": provider_class.MODELS if hasattr(provider_class, 'MODELS') else [],
                    "is_local": provider.is_local,
                })

        return result

    def get_default_provider(self) -> BaseProvider | None:
        """
        Get the default provider.

        Uses the first available provider with a valid API key,
        preferring Claude > OpenAI > Google.

        Returns:
            Provider instance or None if no providers available
        """
        # Preferred order
        preferred_order = ["anthropic", "openai", "google"]

        for api_type in preferred_order:
            try:
                return self.get_provider(api_type)
            except ProviderError:
                continue

        return None

    async def validate_api_key(
        self,
        provider_name: str,
        api_key: str,
    ) -> bool:
        """
        Validate an API key for a provider (AI or search).

        Args:
            provider_name: Provider name
            api_key: API key to validate

        Returns:
            True if key is valid, False otherwise
        """
        # Check if it's an AI provider
        if provider_name in _PROVIDERS:
            provider_class = _PROVIDERS[provider_name]
            provider = provider_class(api_key=api_key)
            return await provider.validate_key()

        # Check if it's a search provider
        search_validators = {
            "brave_search": self._validate_brave_key,
            "youtube": self._validate_youtube_key,
            "listen_notes": self._validate_listen_notes_key,
        }

        if provider_name in search_validators:
            return await search_validators[provider_name](api_key)

        return False

    async def _validate_brave_key(self, api_key: str) -> bool:
        """Validate Brave Search API key."""
        try:
            from app.services.ai.search.brave import BraveSearchClient
            client = BraveSearchClient(api_key)
            # Try a minimal search to validate
            results = await client.search("test", max_results=1)
            return True
        except Exception:
            return False

    async def _validate_youtube_key(self, api_key: str) -> bool:
        """Validate YouTube Data API key."""
        try:
            from app.services.ai.search.youtube import YouTubeSearchClient
            client = YouTubeSearchClient(api_key)
            # Try a minimal search to validate
            results = await client.search("test", max_results=1)
            return True
        except Exception:
            return False

    async def _validate_listen_notes_key(self, api_key: str) -> bool:
        """Validate Listen Notes API key."""
        try:
            from app.services.ai.search.listen_notes import ListenNotesClient
            client = ListenNotesClient(api_key)
            # Try a minimal search to validate
            results = await client.search("test", max_results=1)
            return True
        except Exception:
            return False

    @staticmethod
    def get_supported_providers() -> list[str]:
        """Get list of supported provider names."""
        return list(_PROVIDERS.keys())

    @staticmethod
    def get_provider_models(provider_name: str) -> list[str]:
        """Get list of available models for a provider."""
        if provider_name not in _PROVIDERS:
            return []

        provider_class = _PROVIDERS[provider_name]
        if hasattr(provider_class, 'MODELS'):
            return provider_class.MODELS.copy()
        return []


def get_provider_factory(db: Session) -> ProviderFactory:
    """
    Get a provider factory instance.

    Args:
        db: Database session

    Returns:
        ProviderFactory instance
    """
    return ProviderFactory(db)
