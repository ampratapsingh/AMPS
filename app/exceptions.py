"""Safe errors shared by platform adapters."""

from collections.abc import Iterable
from urllib.parse import quote, quote_plus

import httpx


class PlatformError(Exception):
    """A platform failure that can be described to the API caller."""


class PlatformConfigError(PlatformError):
    """A platform is missing required configuration."""


class PlatformAuthError(PlatformError):
    """The provider rejected authentication or authorization."""


class PlatformRateLimitError(PlatformError):
    """The provider rejected the request due to a rate limit."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        message = "Rate limited"
        if retry_after is not None:
            message += f", retry after {retry_after}s"
        super().__init__(message)


class PlatformAPIError(PlatformError):
    """The provider reported a failed request."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        message = f"Platform API error (HTTP {status_code})"
        if detail:
            message += f": {detail}"
        super().__init__(message)


def redact(message: str, secrets: Iterable[str]) -> str:
    """Mask credentials, including their URL-encoded forms."""
    variants = {
        variant
        for secret in secrets
        if secret
        for variant in (secret, quote(secret, safe=""), quote_plus(secret, safe=""))
    }
    for variant in sorted(variants, key=len, reverse=True):
        message = message.replace(variant, "***")
    return message


def error_snippet(value: object, secrets: Iterable[str]) -> str:
    """Return a short single-line provider message."""
    if not isinstance(value, str):
        return ""
    return " ".join(redact(value, secrets).split())[:160]


def map_api_error(
    status_code: int,
    detail: str = "",
    retry_after: object = None,
) -> PlatformError:
    """Convert a status code into a platform exception."""
    if status_code == 401:
        return PlatformAuthError("Authentication failed")
    if status_code == 403:
        return PlatformAuthError("Access forbidden")
    if status_code == 429:
        retry = str(retry_after)
        seconds = int(retry) if retry.isascii() and retry.isdecimal() and len(retry) <= 10 else None
        return PlatformRateLimitError(seconds)
    return PlatformAPIError(status_code, detail)


def map_http_error(response: httpx.Response, secrets: Iterable[str]) -> PlatformError:
    """Map a failed HTTP response using known JSON error fields only."""
    try:
        data = response.json()
    except ValueError:
        data = {}
    detail = ""
    if isinstance(data, dict):
        for key in ("error_description", "description", "message", "error"):
            detail = error_snippet(data.get(key), secrets)
            if detail:
                break
    return map_api_error(response.status_code, detail, response.headers.get("Retry-After"))
