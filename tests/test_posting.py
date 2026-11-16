import httpx
import pytest
import respx

from app.exceptions import PlatformAuthError
from app.main import app, get_posting_service
from app.services.posting_service import PostingService
from conftest import NOW, PAYLOAD, FakePlatform


async def test_swagger_ui_is_available(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


@pytest.mark.parametrize(
    ("failures", "expected_success", "statuses"),
    [
        (set(), True, ["success", "success"]),
        ({"second"}, True, ["success", "failed"]),
        ({"first", "second"}, False, ["failed", "failed"]),
    ],
)
async def test_posting(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    failures: set[str],
    expected_success: bool,
    statuses: list[str],
) -> None:
    platforms = [
        FakePlatform(name, error=PlatformAuthError("Authentication failed") if name in failures else None)
        for name in ("first", "second")
    ]
    monkeypatch.setitem(
        app.dependency_overrides, get_posting_service,
        lambda: PostingService(platforms, 1, lambda: NOW),
    )

    response = await api_client.post("/posting", json={"message": f" {PAYLOAD.text} "})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is expected_success
    assert [result["platform"] for result in body["results"]] == ["first", "second"]
    assert [result["status"] for result in body["results"]] == statuses
    assert all(platform.received == PAYLOAD for platform in platforms)


async def test_posting_validation_error(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform = FakePlatform("test")
    monkeypatch.setitem(
        app.dependency_overrides, get_posting_service, lambda: PostingService([platform], 1)
    )
    response = await api_client.post("/posting", json={"message": "https://a.com https://b.com"})
    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": "validation_error",
        "details": [{"field": "message", "message": "message must contain exactly one link (found 2)"}],
    }
    assert platform.received is None


async def test_openapi_documents_the_contract(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert list(schema["paths"]) == ["/posting"]
    responses = schema["paths"]["/posting"]["post"]["responses"]
    assert set(responses) == {"200", "422"}
    assert set(responses["200"]["content"]["application/json"]["examples"]) == {"success", "partial"}
    request = schema["components"]["schemas"]["PostRequest"]
    assert request["properties"]["message"]["type"] == "string"
    assert request["examples"][0]["message"].endswith("https://example.com")


async def test_lifespan_builds_real_adapters_and_probes_anonymously(
    monkeypatch: pytest.MonkeyPatch, no_external_http: respx.MockRouter
) -> None:
    from app import main
    from app.config import Settings

    settings = Settings(
        _env_file=None, enabled_platforms="telegram, gist", github_token="fake-gist-test-value"
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    gist_url = "https://gist.github.com/author/demo"
    no_external_http.post("https://api.github.com/gists").respond(201, json={"html_url": gist_url})
    probe = no_external_http.get(gist_url).respond(
        302, headers={"location": f"{gist_url}/view", "set-cookie": "session=mock; Path=/"}
    )
    redirected = no_external_http.get(f"{gist_url}/view").respond(200)
    application = main.create_app()
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post("/posting", json={"message": PAYLOAD.text})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    gist, telegram = body["results"]
    assert gist["platform"] == "GitHub Gist"
    assert gist["posted_url"] == gist_url
    assert gist["public_access"] is True
    assert telegram["platform"] == "Telegram"
    assert telegram["error"] == "Credentials not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL"
    assert "authorization" not in probe.calls.last.request.headers
    assert "cookie" not in redirected.calls.last.request.headers


async def test_unknown_platform_rejected_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main
    from app.config import Settings

    monkeypatch.setattr(main, "get_settings", lambda: Settings(enabled_platforms="unknown", _env_file=None))
    application = main.create_app()
    with pytest.raises(ValueError, match="Unknown ENABLED_PLATFORMS keys: unknown"):
        async with application.router.lifespan_context(application):
            pass
