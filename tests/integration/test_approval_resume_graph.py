from collections.abc import Callable
from decimal import Decimal

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import InMemoryPublisher, make_envelope
from revenueflow.main import app
from revenueflow.repositories.db import fetchone, read_connection
from revenueflow.services import approval as approval_svc
from revenueflow.worker import process_approval_decided, process_event, set_graph

SignedWebhook = Callable[[str], tuple[bytes, str]]

_PHONE = "5511999999999"
_BIG_DISCOUNT = "qual o preço da bomba com 40% de desconto?"


async def _pause_at_approval(
    client: AsyncClient,
    publisher: InMemoryPublisher,
    fake: FakeOutbound,
    signed_webhook: SignedWebhook,
) -> str:
    body, signature = signed_webhook(_BIG_DISCOUNT)
    resp = await client.post(
        "/webhook/whatsapp", content=body, headers={"X-Hub-Signature-256": signature}
    )
    assert resp.status_code == 202
    for _topic, envelope in list(publisher.published):
        await process_event(envelope, outbound=fake)
    async with read_connection() as conn:
        srow = await fetchone(
            conn,
            "SELECT conversation_id FROM conversation_session WHERE phone = %s",
            (_PHONE,),
        )
        assert srow is not None
        arow = await fetchone(
            conn,
            "SELECT approval_id FROM approval WHERE conversation_id = %s",
            (srow["conversation_id"],),
        )
        assert arow is not None
    return str(arow["approval_id"])


async def test_resume_applies_approval_and_sends_once(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            set_graph(build_graph(MemorySaver()))
            approval_id = await _pause_at_approval(client, publisher, fake, signed_webhook)
            assert len(fake.sent) == 1

            publisher.clear()
            fake.sent.clear()
            result = await approval_svc.decide(
                approval_id, "approve_with_override", Decimal("0.10")
            )
            assert result == {"published": True, "status": "APPROVED"}

            decided = [e for _, e in publisher.published if e.event_type == "approval_decided"]
            assert len(decided) == 1
            assert await process_approval_decided(decided[0], outbound=fake) is True
            assert await process_approval_decided(decided[0], outbound=fake) is False

            async with read_connection() as conn:
                srow = await fetchone(
                    conn,
                    "SELECT status FROM approval WHERE approval_id = %s",
                    (approval_id,),
                )
    finally:
        reset_outbound(token)

    assert len(fake.sent) == 1
    assert "10%" in fake.sent[0]["text"]
    assert srow is not None and srow["status"] == "APPROVED"


async def test_new_message_while_awaiting_approval_is_held(
    db: None,
    whatsapp_settings: str,
    publisher: InMemoryPublisher,
    signed_webhook: SignedWebhook,
) -> None:
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            set_graph(build_graph(MemorySaver()))
            await _pause_at_approval(client, publisher, fake, signed_webhook)
            fake.sent.clear()

            nudge = make_envelope(
                "message_received",
                {"phone": _PHONE, "message_text": "e ai, saiu?", "message_id": "wamid.NUDGE"},
                trace_id="t-nudge",
            )
            assert await process_event(nudge, outbound=fake) is True
    finally:
        reset_outbound(token)

    assert len(fake.sent) == 1
    assert "analise" in fake.sent[0]["text"].lower()
