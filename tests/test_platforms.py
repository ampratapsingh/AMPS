import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.config import Settings
from app.exceptions import PlatformAPIError, PlatformAuthError, PlatformConfigError, PlatformRateLimitError
from app.platforms.gist import GistPlatform
from conftest import PAYLOAD

GIST_API = "https://api.github.com/gists"
GIST_URL = "https://gist.github.com/example/abc123"
GIST_TEST_CREDENTIAL = "fake-gist-test-value"


@pytest.fixture
async def platform_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


async def test_gist(platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter) -> None:
    route = no_external_http.post(GIST_API).respond(201, json={"html_url": GIST_URL})
    settings = Settings(_env_file=None, github_token=GIST_TEST_CREDENTIAL)
    result = await GistPlatform(platform_client, settings).post(PAYLOAD)

    assert result.url == GIST_URL
    assert route.call_count == 1
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {GIST_TEST_CREDENTIAL}"
    assert request.headers["Accept"] == "application/vnd.github+json"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert json.loads(request.content) == {
        "description": PAYLOAD.text[:60],
        "public": True,
        "files": {"message.md": {"content": PAYLOAD.text}},
    }


@pytest.mark.parametrize(
    ("status", "headers", "error_type", "message"),
    [
        (401, {}, PlatformAuthError, "Authentication failed"),
        (429, {"Retry-After": "7"}, PlatformRateLimitError, "Rate limited, retry after 7s"),
        (422, {}, PlatformAPIError, "Platform API error (HTTP 422): Rejected as spam ***"),
    ],
)
async def test_gist_error_mapping(
    platform_client: httpx.AsyncClient,
    no_external_http: respx.MockRouter,
    status: int,
    headers: dict[str, str],
    error_type: type[Exception],
    message: str,
) -> None:
    route = no_external_http.post(GIST_API).respond(
        status, headers=headers, json={"message": f"Rejected as spam {GIST_TEST_CREDENTIAL}"}
    )
    settings = Settings(_env_file=None, github_token=GIST_TEST_CREDENTIAL)
    with pytest.raises(error_type) as error:
        await GistPlatform(platform_client, settings).post(PAYLOAD)
    assert str(error.value) == message
    assert route.call_count == 1


async def test_gist_missing_credentials(platform_client: httpx.AsyncClient) -> None:
    settings = Settings(_env_file=None, github_token=None)
    with pytest.raises(PlatformConfigError, match="Credentials not configured: set GITHUB_TOKEN"):
        await GistPlatform(platform_client, settings).post(PAYLOAD)
