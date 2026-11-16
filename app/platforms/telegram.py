"""Publish a message to a public Telegram channel."""

from typing import Any

import httpx

from app.exceptions import error_snippet, map_api_error
from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload


class TelegramPlatform(BasePlatform):
    """Send a bot message and construct its public channel URL."""

    name = "Telegram"

    def _message_result(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("ok") is False:
            code = data.get("error_code")
            if not isinstance(code, int):
                code = response.status_code
            parameters = data.get("parameters")
            retry_after = parameters.get("retry_after") if isinstance(parameters, dict) else None
            detail = error_snippet(data.get("description"), self.secrets())
            raise map_api_error(code, detail, retry_after or response.headers.get("Retry-After"))
        return self.response_data(response)["result"]

    async def post(self, payload: PostPayload) -> PostedContent:
        """Send the original message text and return its t.me URL."""
        self.require_config("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL")
        token = self.settings.telegram_bot_token
        channel = self.settings.telegram_channel
        assert token is not None and channel is not None
        channel = channel.removeprefix("@")
        response = await self.client.post(
            f"https://api.telegram.org/bot{token.get_secret_value()}/sendMessage",
            json={"chat_id": f"@{channel}", "text": payload.text},
        )
        result = self._message_result(response)
        return PostedContent(url=f"https://t.me/{channel}/{result['message_id']}")
