from collections.abc import Callable

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import InMemoryPublisher
from revenueflow.main import app
from revenueflow.repositories.db import fetchall, fetchone, read_connection
from revenueflow.worker import process_event, set_graph

SignedWebhook = Callable[[str], tuple[bytes, str]]

_PHONE = "5511999999999"
_BIG_DISCOUNT = "qual o preço da bomba com 40% de desconto?"


async def test_negotiation_e2e_opens_one_approval_and_is_idempotent(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    body, signature = signed_webhook(_BIG_DISCOUNT)
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

            envelopes = [envelope for _topic, envelope in publisher.published]
            for envelope in envelopes:
                assert await process_event(envelope, outbound=fake) is True
            for envelope in envelopes:
                assert await process_event(envelope, outbound=fake) is False

            async with read_connection() as conn:
                session_row = await fetchone(
                    conn,
                    "SELECT conversation_id, status FROM conversation_session WHERE phone = %s",
                    (_PHONE,),
                )
                assert session_row is not None
                approvals = await fetchall(
                    conn,
                    "SELECT status FROM approval WHERE conversation_id = %s",
                    (session_row["conversation_id"],),
                )
    finally:
        reset_outbound(token)

    assert len(fake.sent) == 1
    assert "aprova" in fake.sent[0]["text"].lower()
    assert session_row["status"] == "OPEN"
    assert len(approvals) == 1
    assert approvals[0]["status"] == "PENDING"
