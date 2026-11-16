import httpx
import pytest

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
