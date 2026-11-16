"""Environment-backed configuration for the posting service."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load configuration from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    enabled_platforms: str = "bluesky,mastodon,devto,gist,telegram,telegraph"
    platform_timeout_seconds: float = Field(default=15, gt=0, allow_inf_nan=False)

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None
    mastodon_base_url: str = "https://mastodon.social"
    mastodon_access_token: SecretStr | None = None
    devto_api_key: SecretStr | None = None
    github_token: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_channel: str | None = None
    telegraph_access_token: SecretStr | None = None
    discord_webhook_url: SecretStr | None = None
    discord_guild_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Read configuration once per process."""
    return Settings()
