import httpx
import pytest
import respx


@pytest.fixture(autouse=True)
def no_external_http() -> respx.MockRouter:
    """Fail unmatched HTTPX requests instead of reaching the network."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
async def api_client() -> httpx.AsyncClient:
    from app.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
