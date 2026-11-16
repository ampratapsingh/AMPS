"""Select the enabled platform adapters in a stable order."""

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.gist import GistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
from app.platforms.telegraph import TelegraphPlatform

ADAPTERS: dict[str, type[BasePlatform]] = {
    "bluesky": BlueskyPlatform,
    "mastodon": MastodonPlatform,
    "devto": DevToPlatform,
    "gist": GistPlatform,
    "telegram": TelegramPlatform,
    "telegraph": TelegraphPlatform,
    "discord": DiscordPlatform,
}


def build_platforms(settings: Settings, client: httpx.AsyncClient) -> list[BasePlatform]:
    """Build enabled adapters and reject unknown configuration keys."""
    enabled = {
        key.strip().lower() for key in settings.enabled_platforms.split(",") if key.strip()
    }
    unknown = enabled.difference(ADAPTERS)
    if unknown:
        raise ValueError(f"Unknown ENABLED_PLATFORMS keys: {', '.join(sorted(unknown))}")
    return [adapter(client, settings) for key, adapter in ADAPTERS.items() if key in enabled]
