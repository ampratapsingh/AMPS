"""Publish concurrently and isolate failures by platform."""

import asyncio
import logging
import traceback
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from time import monotonic

import httpx

from app.exceptions import PlatformError, redact
from app.platforms.base import BasePlatform
from app.schemas import PostResponse, PostResult
from app.validation import PostPayload

logger = logging.getLogger(__name__)


class PostingService:
    """Coordinate one publication attempt per enabled platform."""

    def __init__(
        self,
        platforms: Sequence[BasePlatform],
        timeout_seconds: float,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.platforms = list(platforms)
        self.timeout_seconds = timeout_seconds
        self.clock = clock

    @staticmethod
    def _failed(platform: BasePlatform, error: str) -> PostResult:
        return PostResult(
            platform=platform.name,
            status="failed",
            posted_url=None,
            public_access=False,
            date=None,
            time=None,
            error=error,
        )

    async def _post(self, platform: BasePlatform, payload: PostPayload, started: float) -> PostResult:
        # Retrying a POST could publish a duplicate after an ambiguous failure.
        content = await asyncio.wait_for(platform.post(payload), self.timeout_seconds)
        now = self.clock().astimezone(timezone.utc)
        remaining = self.timeout_seconds - (monotonic() - started)
        public = False
        if remaining > 0:
            try:
                public = await asyncio.wait_for(platform.verify_public(content.url), remaining)
            except Exception:
                # An unsuccessful probe does not undo a completed publication.
                pass
        return PostResult(
            platform=platform.name,
            status="success",
            posted_url=content.url,
            public_access=public,
            date=now.date().isoformat(),
            time=now.strftime("%H:%M:%S"),
            error=None,
        )

    async def _safe_post(self, platform: BasePlatform, payload: PostPayload) -> PostResult:
        started = monotonic()
        try:
            result = await self._post(platform, payload, started)
        except asyncio.TimeoutError:
            result = self._failed(platform, f"Timed out after {self.timeout_seconds:g}s")
        except httpx.TimeoutException:
            result = self._failed(platform, "Request timed out")
        except httpx.HTTPError:
            result = self._failed(platform, "Network error")
        except PlatformError as exc:
            result = self._failed(platform, redact(str(exc), platform.secrets()))
        except Exception as exc:
            # Traceback frames help diagnose failures without logging the exception payload.
            frames = "".join(traceback.format_tb(exc.__traceback__))
            logger.error("%s raised %s\n%s", platform.name, type(exc).__name__, frames)
            result = self._failed(platform, "Unexpected error")

        logger.info("%s %s %.1f ms", platform.name, result.status, (monotonic() - started) * 1000)
        return result

    async def publish(self, payload: PostPayload) -> PostResponse:
        """Return one result per platform in registry order."""
        outcomes = await asyncio.gather(
            *(self._safe_post(platform, payload) for platform in self.platforms),
            return_exceptions=True,
        )
        results = [
            outcome if isinstance(outcome, PostResult) else self._failed(platform, "Unexpected error")
            for platform, outcome in zip(self.platforms, outcomes)
        ]
        return PostResponse(
            success=any(result.status == "success" for result in results), results=results
        )
