"""Publish a Bluesky post with a clickable CTA facet."""

from datetime import datetime, timezone

from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload, split_link

XRPC = "https://bsky.social/xrpc"
POST_TYPE = "app.bsky.feed.post"


class BlueskyPlatform(BasePlatform):
    """Authenticate via the Bluesky PDS and create a feed record."""

    name = "Bluesky"

    async def post(self, payload: PostPayload) -> PostedContent:
        """Create a post and return its bsky.app URL."""
        self.require_config("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
        password = self.settings.bluesky_app_password
        assert password is not None
        response = await self.client.post(
            f"{XRPC}/com.atproto.server.createSession",
            json={
                "identifier": self.settings.bluesky_handle,
                "password": password.get_secret_value(),
            },
        )
        session = self.response_data(response)
        jwt = session["accessJwt"]
        before, _ = split_link(payload)
        # AT Protocol facet indices count UTF-8 bytes.
        start = len(before.encode("utf-8"))
        end = start + len(payload.link.encode("utf-8"))
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        response = await self.client.post(
            f"{XRPC}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "repo": session["did"],
                "collection": POST_TYPE,
                "record": {
                    "$type": POST_TYPE,
                    "text": payload.text,
                    "createdAt": created_at,
                    "facets": [{
                        "index": {"byteStart": start, "byteEnd": end},
                        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": payload.link}],
                    }],
                },
            },
        )
        key = self.response_data(response, jwt)["uri"].rsplit("/", 1)[-1]
        return PostedContent(url=f"https://bsky.app/profile/{session['handle']}/post/{key}")
