"""Publish the message as a public GitHub Gist."""

from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload


class GistPlatform(BasePlatform):
    """Create a public Markdown gist."""

    name = "GitHub Gist"

    async def post(self, payload: PostPayload) -> PostedContent:
        """Create a gist and return its HTML URL."""
        self.require_config("GITHUB_TOKEN")
        token = self.settings.github_token
        assert token is not None
        response = await self.client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": payload.text[:60],
                "public": True,
                "files": {"message.md": {"content": payload.text}},
            },
        )
        return PostedContent(url=self.response_data(response)["html_url"])
