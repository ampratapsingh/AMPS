"""Publish the message as a Dev.to article."""

from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload, split_link


def make_title(payload: PostPayload) -> str:
    """Use up to eight whole words and eighty characters outside the CTA."""
    before, after = split_link(payload)
    words = f"{before} {after}".split()
    title = ""
    for word in words[:8]:
        candidate = f"{title} {word}".strip()
        if len(candidate) > 80:
            break
        title = candidate
    return title or "Shared link"


class DevToPlatform(BasePlatform):
    """Create a published article through the Forem API."""

    name = "Dev.to"

    async def post(self, payload: PostPayload) -> PostedContent:
        """Publish the article and return its public URL."""
        self.require_config("DEVTO_API_KEY")
        key = self.settings.devto_api_key
        assert key is not None
        response = await self.client.post(
            "https://dev.to/api/articles",
            headers={"api-key": key.get_secret_value(), "Accept": "application/vnd.forem.api-v1+json"},
            json={
                "article": {
                    "title": make_title(payload),
                    "body_markdown": payload.text,
                    "published": True,
                }
            },
        )
        return PostedContent(url=self.response_data(response)["url"])
