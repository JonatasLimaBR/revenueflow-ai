import re
from collections.abc import Iterator

import pytest
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import EventEnvelope, make_envelope
from revenueflow.repositories.db import fetchone, read_connection
from revenueflow.worker import process_event, set_graph

_PRICE = re.compile(r"\d+[.,]\d{2}")
_PHONE = "+5511999999999"


@pytest.fixture
def outbound() -> Iterator[FakeOutbound]:
    set_graph(build_graph(MemorySaver()))
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        yield fake
    finally:
        reset_outbound(token)


def _envelope() -> EventEnvelope:
    return make_envelope(
        "message_received",
        {
            "event_id": "e1",
            "occurred_at": "2026-08-29T12:00:00+00:00",
            "phone": _PHONE,
            "message_id": "wamid.1",
            "message_type": "text",
            "message_text": "quero uma bomba d'agua 1cv",
        },
        trace_id="t1",
    )


async def test_process_event_replies_and_persists(db: None, outbound: FakeOutbound) -> None:
    env = _envelope()

    assert await process_event(env, outbound=outbound) is True

    assert len(outbound.sent) == 1
    text = outbound.sent[0]["text"]
    assert text
    assert "1CV" in text
    assert "R$" not in text
    assert _PRICE.search(text) is None

    async with read_connection() as conn:
        session_row = await fetchone(
            conn,
            "SELECT conversation_id FROM conversation_session WHERE phone = %s",
            (_PHONE,),
        )
        lead_row = await fetchone(conn, "SELECT lead_id FROM lead WHERE phone = %s", (_PHONE,))
    assert session_row is not None
    assert lead_row is not None

    assert await process_event(env, outbound=outbound) is False
    assert len(outbound.sent) == 1


async def test_session_in_handoff_short_circuits(db: None, outbound: FakeOutbound) -> None:
    from uuid import uuid4

    from revenueflow.domain.models import SessionStatus
    from revenueflow.repositories import session as session_repo
    from revenueflow.repositories.db import unit_of_work
    from revenueflow.services import get_or_create

    phone = f"+5511{uuid4().hex[:9]}"
    session = await get_or_create(phone)
    async with unit_of_work() as conn:
        await session_repo.update_status(conn, session.conversation_id, SessionStatus.HUMAN_HANDOFF)

    env = make_envelope(
        "message_received",
        {
            "event_id": "e-hoff",
            "occurred_at": "2026-08-29T12:00:00+00:00",
            "phone": phone,
            "message_id": "wamid.hoff",
            "message_type": "text",
            "message_text": "ainda ai?",
        },
        trace_id="t-hoff",
    )

    assert await process_event(env, outbound=outbound) is True
    assert len(outbound.sent) == 1
    assert "atendente humano" in outbound.sent[0]["text"]

    assert await process_event(env, outbound=outbound) is False
    assert len(outbound.sent) == 1
