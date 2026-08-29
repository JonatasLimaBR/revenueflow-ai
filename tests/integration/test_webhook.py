from collections.abc import Callable

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revenueflow.events import InMemoryPublisher
from revenueflow.main import app

SignedWebhook = Callable[[str], tuple[bytes, str]]


async def test_post_valid_signature_publishes(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    body, signature = signed_webhook("quero uma bomba d'agua 1cv")
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": signature},
        )

    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}
    assert len(publisher.published) == 1
    topic, envelope = publisher.published[0]
    assert topic == "revenueflow.messages"
    assert envelope.event_type == "message_received"
    assert envelope.payload["message_text"] == "quero uma bomba d'agua 1cv"


async def test_post_wrong_signature_rejected(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    body, _ = signed_webhook("quero uma bomba d'agua 1cv")
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=deadbeef"},
        )

    assert resp.status_code == 403
    assert publisher.published == []


async def test_get_verify_handshake(db: None, whatsapp_settings: str) -> None:
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        ok = await client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": whatsapp_settings,
                "hub.challenge": "xyz",
            },
        )
        bad = await client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "not-the-token",
                "hub.challenge": "xyz",
            },
        )

    assert ok.status_code == 200
    assert ok.text == "xyz"
    assert bad.status_code == 403
