"""Common interface and HTTP behavior for platform adapters."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, SecretStr

from app.config import Settings
from app.exceptions import PlatformAPIError, PlatformConfigError, map_http_error
from app.validation import PostPayload


class PostedContent(BaseModel):
    """The link returned after the provider creates a post."""

    url: str


class BasePlatform(ABC):
    """Publish through one provider and check the resulting link."""

    name: ClassVar[str]

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    @abstractmethod
    async def post(self, payload: PostPayload) -> PostedContent:
        """Publish the message or raise a platform error."""

    def secrets(self) -> tuple[str, ...]:
        """Read configured secret values when redacting a provider error."""
        return tuple(
            value.get_secret_value()
            for field in type(self.settings).model_fields
            if isinstance(value := getattr(self.settings, field), SecretStr)
        )

    def require_config(self, *names: str) -> None:
        """Raise a readable error when required environment variables are absent."""
        if any(not getattr(self.settings, name.lower()) for name in names):
            raise PlatformConfigError(f"Credentials not configured: set {' and '.join(names)}")

    def response_data(self, response: httpx.Response, *additional_secrets: str) -> dict[str, Any]:
        """Read a successful JSON response or raise a safe provider error."""
        if not response.is_success:
            raise map_http_error(response, (*self.secrets(), *additional_secrets))
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise PlatformAPIError(response.status_code, "Invalid JSON response")
        return data

    async def verify_public(self, url: str) -> bool:
        """Probe the URL anonymously and retry a non-2xx response once."""
        try:
            for attempt in range(2):
                if attempt:
                    await asyncio.sleep(1)
                response = await self.client.get(url, follow_redirects=True, timeout=3.0)
                if response.is_success:
                    return True
        except Exception:
            return False
        return False
