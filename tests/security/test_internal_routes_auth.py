import pytest
from httpx import ASGITransport, AsyncClient

from revenueflow.config import get_settings
from revenueflow.main import app

_ROUTES = [
    ("GET", "/internal/approvals"),
    ("POST", "/internal/approvals/x"),
    ("GET", "/internal/handoffs"),
    ("POST", "/internal/handoffs/x"),
    ("GET", "/internal/audit/c-x"),
]

_TOKENS = ("APPROVAL_API_TOKEN", "HANDOFF_API_TOKEN")


@pytest.fixture
def tokens_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _TOKENS:
        monkeypatch.setenv(name, "test-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def tokens_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _TOKENS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _call(method: str, path: str, headers: dict[str, str] | None = None) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.request(method, path, headers=headers)
    return response.status_code


@pytest.mark.parametrize(("method", "path"), _ROUTES)
async def test_missing_bearer_is_401(method: str, path: str, tokens_set: None) -> None:
    assert await _call(method, path) == 401


@pytest.mark.parametrize(("method", "path"), _ROUTES)
async def test_wrong_bearer_is_401(method: str, path: str, tokens_set: None) -> None:
    assert await _call(method, path, {"Authorization": "Bearer nope"}) == 401


@pytest.mark.parametrize(("method", "path"), _ROUTES)
async def test_unconfigured_token_is_503(method: str, path: str, tokens_unset: None) -> None:
    assert await _call(method, path) == 503
