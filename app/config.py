"""
Application configuration using pydantic-settings.
Loads values from .env file in project root.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "perunsblackbook"
    db_user: str = "blackbook"
    db_password: str = ""

    # Application settings
    secret_key: str = "change-me-in-production"
    debug: bool = False

    # Google OAuth settings
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # Encryption settings (for OAuth token storage)
    encryption_key: str = ""

    # AI Provider settings
    ai_default_provider: str = "anthropic"
    ai_max_context_tokens: int = 4000
    ai_streaming_enabled: bool = True

    # Optional: Direct API keys (alternative to database-stored keys)
    # These are optional - keys can also be stored encrypted in the database
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""

    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy database URL."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def google_oauth_configured(self) -> bool:
        """Check if Google OAuth is properly configured."""
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def encryption_configured(self) -> bool:
        """Check if encryption key is configured."""
        return bool(self.encryption_key)

    @property
    def ai_provider_configured(self) -> bool:
        """Check if any AI provider API key is configured via environment."""
        return bool(
            self.openai_api_key or
            self.anthropic_api_key or
            self.google_ai_api_key
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
