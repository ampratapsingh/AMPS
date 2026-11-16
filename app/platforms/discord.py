"""Publish to a Discord channel through a configured webhook."""

import httpx

from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload


class DiscordPlatform(BasePlatform):
    """Execute a webhook and return the channel message link."""

    name = "Discord"

    async def post(self, payload: PostPayload) -> PostedContent:
        """Wait for Discord to return the created message."""
        self.require_config("DISCORD_WEBHOOK_URL", "DISCORD_GUILD_ID")
        webhook = self.settings.discord_webhook_url
        assert webhook is not None
        url = httpx.URL(webhook.get_secret_value()).copy_set_param("wait", "true")
        response = await self.client.post(url, json={"content": payload.text})
        webhook_credential = url.path.rstrip("/").rsplit("/", 1)[-1]
        data = self.response_data(response, str(url), webhook_credential)
        guild = self.settings.discord_guild_id
        return PostedContent(url=f"https://discord.com/channels/{guild}/{data['channel_id']}/{data['id']}")

    async def verify_public(self, url: str) -> bool:
        """Discord message links require login and server membership."""
        return False
