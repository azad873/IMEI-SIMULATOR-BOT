"""
Configuration module using pydantic-settings.

This reads environment variables and makes them available as 'settings'.
"""

from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file if present (useful in local dev)
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    BOT_TOKEN: str  # Telegram bot token
    POSTGRES_DSN: str  # PostgreSQL DSN for asyncpg / SQLAlchemy
    REDIS_URL: str  # Redis connection URL
    ADMIN_IDS: str  # Comma-separated list of admin Telegram user IDs
    SECRET_KEY: str  # Secret key used for HMAC fake-location generator
    GEOAPIFY_API_KEY: str  # Static map provider API key
    WEBHOOK_URL: str | None = None  # Optional webhook URL
    PORT: int = 8080  # Port used when running in webhook mode
    LOCALE_FALLBACK: str = "en"  # Fallback language code

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def admin_ids_list(self) -> List[int]:
        """
        Parse ADMIN_IDS (comma separated) into a list of integers.

        Any non-integer chunks are ignored to keep the bot robust.
        """
        ids: List[int] = []
        for chunk in self.ADMIN_IDS.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                ids.append(int(chunk))
            except ValueError:
                # Skip bad values silently
                continue
        return ids


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# A global ‘settings’ object that's easy to import elsewhere.
settings = get_settings()
