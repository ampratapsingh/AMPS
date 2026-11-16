import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.config import Settings
from app.exceptions import PlatformAPIError, PlatformAuthError, PlatformConfigError, PlatformRateLimitError
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.gist import GistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.validation import validate_message
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


async def test_mastodon(platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter) -> None:
    url = "https://social.example/@author/123"
    route = no_external_http.post("https://social.example/api/v1/statuses").respond(
        200, json={"url": url}
    )
    credential = "fake-mastodon-value"
    settings = Settings(
        _env_file=None, mastodon_base_url="https://social.example/", mastodon_access_token=credential
    )
    result = await MastodonPlatform(platform_client, settings).post(PAYLOAD)

    assert result.url == url
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {credential}"
    assert json.loads(request.content) == {"status": PAYLOAD.text, "visibility": "public"}


async def test_bluesky(platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter) -> None:
    handle = "author.bsky.social"
    credential = "fake-bluesky-value"
    session_jwt = "mock-session"
    xrpc = "https://bsky.social/xrpc"
    session = no_external_http.post(f"{xrpc}/com.atproto.server.createSession").respond(
        200, json={"accessJwt": session_jwt, "did": "did:plc:demo", "handle": handle}
    )
    record = no_external_http.post(f"{xrpc}/com.atproto.repo.createRecord").respond(
        200, json={"uri": "at://did:plc:demo/app.bsky.feed.post/rkey"}
    )
    settings = Settings(_env_file=None, bluesky_handle=handle, bluesky_app_password=credential)
    payload = validate_message("🚀 Read (https://example.com).")
    result = await BlueskyPlatform(platform_client, settings).post(payload)

    assert result.url == f"https://bsky.app/profile/{handle}/post/rkey"
    assert json.loads(session.calls.last.request.content) == {
        "identifier": handle, "password": credential
    }
    request = record.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {session_jwt}"
    content = json.loads(request.content)
    assert content["repo"] == "did:plc:demo"
    assert content["collection"] == content["record"]["$type"] == "app.bsky.feed.post"
    assert content["record"]["text"] == payload.text
    assert content["record"]["createdAt"].endswith("Z")
    assert content["record"]["facets"] == [{
        "index": {"byteStart": 11, "byteEnd": 30},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": payload.link}],
    }]
    assert payload.text.encode("utf-8")[11:30] == payload.link.encode("utf-8")
