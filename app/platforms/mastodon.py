"""Publish a public status to a configured Mastodon instance."""

from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload


class MastodonPlatform(BasePlatform):
    """Create a status on the configured instance."""

    name = "Mastodon"

    async def post(self, payload: PostPayload) -> PostedContent:
        """Create a public status and return its URL."""
        self.require_config("MASTODON_ACCESS_TOKEN")
        token = self.settings.mastodon_access_token
        assert token is not None
        base_url = self.settings.mastodon_base_url.rstrip("/")
        response = await self.client.post(
            f"{base_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {token.get_secret_value()}"},
            json={"status": payload.text, "visibility": "public"},
        )
        return PostedContent(url=self.response_data(response)["url"])
