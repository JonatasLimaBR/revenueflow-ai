import re
from collections.abc import Callable

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import InMemoryPublisher
from revenueflow.main import app
from revenueflow.worker import process_event, set_graph

SignedWebhook = Callable[[str], tuple[bytes, str]]

_PRICE = re.compile(r"\d+[.,]\d{2}")


async def test_webhook_to_outbound_slice(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    body, signature = signed_webhook("quero uma bomba d'agua 1cv")
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            set_graph(build_graph(MemorySaver()))
            resp = await client.post(
                "/webhook/whatsapp",
                content=body,
                headers={"X-Hub-Signature-256": signature},
            )
            assert resp.status_code == 202
            assert publisher.published

            for _topic, envelope in publisher.published:
                await process_event(envelope, outbound=fake)
    finally:
        reset_outbound(token)

    assert len(fake.sent) == 1
    reply = fake.sent[0]["text"]
    assert "1CV" in reply
    assert "R$" not in reply
    assert _PRICE.search(reply) is None
