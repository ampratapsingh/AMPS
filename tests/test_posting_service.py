import asyncio
import logging

import httpx
import pytest

from app.exceptions import PlatformAuthError
from app.platforms.base import PostedContent
from app.services.posting_service import PostingService
from app.validation import PostPayload
from conftest import NOW, PAYLOAD, FakePlatform


async def test_publish_preserves_order_and_uses_utc_clock() -> None:
    second = FakePlatform("second", public=False)

    class FirstPlatform(FakePlatform):
        async def post(self, payload: PostPayload) -> PostedContent:
            await second.completed.wait()
            return await super().post(payload)

    first = FirstPlatform("first")
    response = await PostingService([first, second], 1, lambda: NOW).publish(PAYLOAD)

    assert response.success is True
    assert [result.platform for result in response.results] == ["first", "second"]
    for result in response.results:
        assert result.status == "success"
        assert result.date == "2026-11-16"
        assert result.time == "10:30:00"
        assert result.error is None
    assert [result.public_access for result in response.results] == [True, False]
    assert first.received == second.received == PAYLOAD


@pytest.mark.parametrize(
    ("platform", "error"),
    [
        (FakePlatform("auth", error=PlatformAuthError("Authentication failed")), "Authentication failed"),
        (FakePlatform("slow", delay=1), "Timed out after 0.01s"),
        (FakePlatform("unexpected", error=Exception("private adapter data")), "Unexpected error"),
        (FakePlatform("timeout", error=httpx.ReadTimeout("private URL")), "Request timed out"),
        (FakePlatform("network", error=httpx.ConnectError("private URL")), "Network error"),
    ],
)
async def test_platform_failure_is_isolated(
    platform: FakePlatform, error: str, caplog: pytest.LogCaptureFixture
) -> None:
    good = FakePlatform("good")
    response = await PostingService([platform, good], 0.01).publish(PAYLOAD)

    assert response.success is True
    failure, success = response.results
    assert failure.model_dump() == {
        "platform": platform.name,
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": error,
    }
    assert success.status == "success"
    assert "private" not in caplog.text
    if error == "Unexpected error":
        assert "test_posting_service" in caplog.text or "conftest.py" in caplog.text


async def test_all_platforms_fail() -> None:
    platform = FakePlatform("auth", error=PlatformAuthError("Authentication failed"))
    response = await PostingService([platform], 1).publish(PAYLOAD)
    assert response.success is False


async def test_public_verification_timeout_keeps_success() -> None:
    class SlowProbe(FakePlatform):
        async def verify_public(self, url: str) -> bool:
            await asyncio.sleep(1)
            return True

    response = await PostingService([SlowProbe("slow")], 0.01).publish(PAYLOAD)
    assert response.results[0].status == "success"
    assert response.results[0].public_access is False
