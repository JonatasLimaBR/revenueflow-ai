from httpx import ASGITransport, AsyncClient

from revenueflow.main import app

_EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


async def test_healthz_carries_security_headers() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/healthz")

    for header, value in _EXPECTED.items():
        assert response.headers[header] == value
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")


async def test_headers_present_on_a_404_too() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/definitely-not-a-route")

    assert response.status_code == 404
    assert response.headers["x-frame-options"] == "DENY"
