"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with type-safe environment variables."""

    # Application settings
    app_name: str = "Slack to Vertex AI Middleware"
    environment: str = "development"
    log_level: str = "INFO"

    # Google Cloud Platform
    gcp_project_id: str
    gcp_location: str = "us-central1"

    # Firestore
    firestore_agents_collection: str = "agents"
    firestore_sessions_collection: str = "sessions"

    # Session management
    # Sessions expire after this many minutes of inactivity
    # A new Vertex AI session will be created after expiry
    session_timeout_minutes: int = 30

    # Slack
    slack_signing_secret: str

    # API settings
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance - loaded once per app lifecycle.

    Returns:
        Settings: Application configuration
    """
    return Settings()
