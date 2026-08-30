from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revenueflow.main import app


async def test_healthz_reports_ok(db: None) -> None:
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": True}
