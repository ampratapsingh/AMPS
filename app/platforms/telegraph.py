"""Publish the message as a Telegraph page."""

import asyncio
import json
from typing import Any

import httpx
from pydantic import SecretStr

from app.config import Settings
from app.exceptions import PlatformError, error_snippet
from app.platforms.base import BasePlatform, PostedContent
from app.platforms.devto import make_title
from app.validation import PostPayload, split_link

TELEGRAPH_API = "https://api.telegra.ph"


class TelegraphPlatform(BasePlatform):
    """Create a page using a configured or lazily provisioned account."""

    name = "Telegraph"

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(client, settings)
        self._access_token = settings.telegraph_access_token
        self._account_lock = asyncio.Lock()

    def _result(self, response: httpx.Response, *additional_secrets: str) -> dict[str, Any]:
        data = self.response_data(response, *additional_secrets)
        if data.get("ok") is not True:
            detail = error_snippet(data.get("error"), (*self.secrets(), *additional_secrets))
            raise PlatformError(detail or "Telegraph rejected the request")
        return data["result"]

    async def _get_access_token(self) -> SecretStr:
        async with self._account_lock:
            if not self._access_token:
                response = await self.client.post(
                    f"{TELEGRAPH_API}/createAccount", data={"short_name": "poster"}
                )
                self._access_token = SecretStr(self._result(response)["access_token"])
            return self._access_token

    async def post(self, payload: PostPayload) -> PostedContent:
        """Publish one paragraph with a clickable link."""
        before, after = split_link(payload)
        link = {"tag": "a", "attrs": {"href": payload.link}, "children": [payload.link]}
        content = [{"tag": "p", "children": [part for part in (before, link, after) if part]}]
        token = (await self._get_access_token()).get_secret_value()
        response = await self.client.post(
            f"{TELEGRAPH_API}/createPage",
            data={
                "access_token": token,
                "title": make_title(payload),
                "content": json.dumps(content, ensure_ascii=False),
                "return_content": "false",
            },
        )
        return PostedContent(url=self._result(response, token)["url"])
