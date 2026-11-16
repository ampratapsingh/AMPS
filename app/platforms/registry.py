"""Select the enabled platform adapters in a stable order."""

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.platforms.gist import GistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.telegram import TelegramPlatform

PLATFORM_ORDER = ("bluesky", "mastodon", "devto", "gist", "telegram", "telegraph", "discord")
ADAPTERS: dict[str, type[BasePlatform]] = {
    "gist": GistPlatform,
    "mastodon": MastodonPlatform,
    "bluesky": BlueskyPlatform,
    "devto": DevToPlatform,
    "telegram": TelegramPlatform,
}


def build_platforms(settings: Settings, client: httpx.AsyncClient) -> list[BasePlatform]:
    """Build enabled adapters and reject unknown configuration keys."""
    enabled = {
        key.strip().lower() for key in settings.enabled_platforms.split(",") if key.strip()
    }
    unknown = enabled.difference(PLATFORM_ORDER)
    if unknown:
        raise ValueError(f"Unknown ENABLED_PLATFORMS keys: {', '.join(sorted(unknown))}")
    return [ADAPTERS[key](client, settings) for key in PLATFORM_ORDER if key in enabled and key in ADAPTERS]
