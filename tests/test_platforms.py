import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.config import Settings
from app.exceptions import PlatformAPIError, PlatformAuthError, PlatformConfigError, PlatformRateLimitError
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform, make_title
from app.platforms.gist import GistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
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


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("https://example.com", "Shared link"),
        ("Read   https://example.com  this now", "Read this now"),
        ("one two three four five six seven eight nine https://example.com",
         "one two three four five six seven eight"),
        (f"{'a' * 78} bb https://example.com", "a" * 78),
    ],
)
def test_make_title(text: str, title: str) -> None:
    assert make_title(validate_message(text)) == title


async def test_devto(platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter) -> None:
    url = "https://dev.to/author/read-this-123"
    route = no_external_http.post("https://dev.to/api/articles").respond(201, json={"url": url})
    credential = "fake-forem-value"
    settings = Settings(_env_file=None, devto_api_key=credential)
    result = await DevToPlatform(platform_client, settings).post(PAYLOAD)

    assert result.url == url
    request = route.calls.last.request
    assert request.headers["api-key"] == credential
    assert request.headers["Accept"] == "application/vnd.forem.api-v1+json"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "article": {"title": "Read this", "body_markdown": PAYLOAD.text, "published": True}
    }


async def test_devto_validation_error(
    platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter
) -> None:
    no_external_http.post("https://dev.to/api/articles").respond(422, json={"error": "Duplicate article"})
    settings = Settings(_env_file=None, devto_api_key="fake-forem-value")
    with pytest.raises(PlatformAPIError, match="Duplicate article"):
        await DevToPlatform(platform_client, settings).post(PAYLOAD)


TELEGRAM_TEST_CREDENTIAL = "12345:fake-bot-credential"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TEST_CREDENTIAL}/sendMessage"


@pytest.mark.parametrize("channel", ["@updates", "updates"])
async def test_telegram(
    platform_client: httpx.AsyncClient, no_external_http: respx.MockRouter, channel: str
) -> None:
    route = no_external_http.post(TELEGRAM_API).respond(
        200, json={"ok": True, "result": {"message_id": 123}}
    )
    settings = Settings(
        _env_file=None, telegram_bot_token=TELEGRAM_TEST_CREDENTIAL, telegram_channel=channel
    )
    result = await TelegramPlatform(platform_client, settings).post(PAYLOAD)

    assert result.url == "https://t.me/updates/123"
    assert json.loads(route.calls.last.request.content) == {
        "chat_id": "@updates",
        "text": PAYLOAD.text,
    }


@pytest.mark.parametrize(
    ("status", "code", "error_type", "message"),
    [
        (401, 401, PlatformAuthError, "Authentication failed"),
        (200, 429, PlatformRateLimitError, "Rate limited, retry after 12s"),
        (400, 400, PlatformAPIError, "Platform API error (HTTP 400): Error for ***"),
    ],
)
async def test_telegram_errors(
    platform_client: httpx.AsyncClient,
    no_external_http: respx.MockRouter,
    status: int,
    code: int,
    error_type: type[Exception],
    message: str,
) -> None:
    no_external_http.post(TELEGRAM_API).respond(
        status,
        json={
            "ok": False,
            "error_code": code,
            "description": f"Error for {TELEGRAM_TEST_CREDENTIAL}",
            "parameters": {"retry_after": 12},
        },
    )
    settings = Settings(
        _env_file=None, telegram_bot_token=TELEGRAM_TEST_CREDENTIAL, telegram_channel="updates"
    )
    with pytest.raises(error_type) as error:
        await TelegramPlatform(platform_client, settings).post(PAYLOAD)
    assert str(error.value) == message
