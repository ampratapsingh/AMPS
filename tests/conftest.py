import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.config import Settings
from app.platforms.base import BasePlatform, PostedContent
from app.validation import PostPayload

NOW = datetime(2026, 11, 16, 10, 30, tzinfo=timezone.utc)
PAYLOAD = PostPayload("Read this https://example.com", "https://example.com")


class FakePlatform(BasePlatform):
    def __init__(
        self,
        name: str,
        *,
        error: Exception | None = None,
        delay: float = 0,
        public: bool = True,
    ) -> None:
        self.settings = Settings(_env_file=None)
        self.completed = asyncio.Event()
        self.name = name
        self.error = error
        self.delay = delay
        self.public = public
        self.received: PostPayload | None = None

    async def post(self, payload: PostPayload) -> PostedContent:
        self.received = payload
        if self.delay:
            await asyncio.sleep(self.delay)
        self.completed.set()
        if self.error:
            raise self.error
        return PostedContent(url=f"https://example.com/{self.name}")

    async def verify_public(self, url: str) -> bool:
        return self.public


@pytest.fixture(autouse=True)
def no_external_http() -> Iterator[respx.MockRouter]:
    """Fail unmatched HTTPX requests instead of reaching the network."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
async def api_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    from app import main

    monkeypatch.setattr(main, "get_settings", lambda: Settings(enabled_platforms="", _env_file=None))
    async with main.app.router.lifespan_context(main.app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            yield client
