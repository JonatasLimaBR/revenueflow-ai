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


async def test_resolved_handoff_does_not_leak_into_the_next_turn(
    db: None, outbound: FakeOutbound
) -> None:
    # Found live (2026-09-09): the checkpointer merges state_in onto the
    # persisted state, and `handoff` was only ever set True, never reset --
    # once a thread handed off once, route_after_classify short-circuited to
    # handoff_node on every later turn forever, even after the Handoff and
    # the session were resolved (resolving only touches the DB, never the
    # checkpoint's `handoff` key). A fresh turn must start its own routing
    # decision from scratch.
    from uuid import uuid4

    from revenueflow.domain.models import SessionStatus
    from revenueflow.repositories import session as session_repo
    from revenueflow.repositories.db import unit_of_work

    phone = f"+5511{uuid4().hex[:9]}"
    handoff_env = make_envelope(
        "message_received",
        {
            "event_id": "e-stale-1",
            "occurred_at": "2026-08-29T12:00:00+00:00",
            "phone": phone,
            "message_id": "wamid.stale.1",
            "message_type": "text",
            "message_text": "quero falar com um atendente",
        },
        trace_id="t-stale-1",
    )
    assert await process_event(handoff_env, outbound=outbound) is True
    assert "atendente humano" in outbound.sent[-1]["text"]

    async with unit_of_work() as conn:
        session_row = await fetchone(
            conn, "SELECT conversation_id FROM conversation_session WHERE phone = %s", (phone,)
        )
        assert session_row is not None
        await session_repo.update_status(conn, session_row["conversation_id"], SessionStatus.OPEN)

    normal_env = make_envelope(
        "message_received",
        {
            "event_id": "e-stale-2",
            "occurred_at": "2026-08-29T12:05:00+00:00",
            "phone": phone,
            "message_id": "wamid.stale.2",
            "message_type": "text",
            "message_text": "quero uma bomba d'agua 1cv",
        },
        trace_id="t-stale-2",
    )
    assert await process_event(normal_env, outbound=outbound) is True

    reply = outbound.sent[-1]["text"]
    assert "atendente humano" not in reply
    assert "1CV" in reply


async def test_resolved_approval_does_not_leak_into_the_next_turn(
    db: None, outbound: FakeOutbound
) -> None:
    # Found live (2026-09-11): the exact same leak as the handoff flag above,
    # one field over. `negotiation_node` sets `pending_approval_id` only when
    # IT creates a fresh Approval; every other branch (a plain quote, an
    # in-policy discount) returns no such key, so the checkpoint merge left a
    # long-resolved approval's id in place. `route_after_negotiation` then
    # routed to `await_approval` off that stale truthy value on the very next
    # unrelated price question, reopening `interrupt()` against an approval
    # nobody could ever act on again -- the conversation got stuck on "ainda
    # esta em analise" forever, with no Approval left to decide.
    from uuid import uuid4

    from revenueflow.events import make_envelope
    from revenueflow.repositories.db import fetchone, read_connection
    from revenueflow.worker import get_graph, process_approval_decided

    phone = f"+5511{uuid4().hex[:9]}"
    out_of_policy_env = make_envelope(
        "message_received",
        {
            "event_id": "e-appr-1",
            "occurred_at": "2026-08-29T12:00:00+00:00",
            "phone": phone,
            "message_id": "wamid.appr.1",
            "message_type": "text",
            "message_text": "qual o preço da bomba com 40% de desconto?",
        },
        trace_id="t-appr-1",
    )
    assert await process_event(out_of_policy_env, outbound=outbound) is True

    async with read_connection() as conn:
        session_row = await fetchone(
            conn, "SELECT conversation_id FROM conversation_session WHERE phone = %s", (phone,)
        )
        assert session_row is not None
        conversation_id = session_row["conversation_id"]
        approval_row = await fetchone(
            conn,
            "SELECT approval_id FROM approval WHERE conversation_id = %s",
            (conversation_id,),
        )
    assert approval_row is not None

    decided_env = make_envelope(
        "approval_decided",
        {
            "approval_id": approval_row["approval_id"],
            "conversation_id": conversation_id,
            "decision": "reject",
            "discount_pct": None,
        },
        trace_id="t-appr-decide",
    )
    assert await process_approval_decided(decided_env, outbound=outbound) is True

    followup_env = make_envelope(
        "message_received",
        {
            "event_id": "e-appr-2",
            "occurred_at": "2026-08-29T12:05:00+00:00",
            "phone": phone,
            "message_id": "wamid.appr.2",
            "message_type": "text",
            "message_text": "qual o preço da bomba?",
        },
        trace_id="t-appr-2",
    )
    assert await process_event(followup_env, outbound=outbound) is True

    config = {"configurable": {"thread_id": conversation_id}}
    snapshot = await get_graph().aget_state(config)
    assert "await_approval" not in (snapshot.next or ())

    third_env = make_envelope(
        "message_received",
        {
            "event_id": "e-appr-3",
            "occurred_at": "2026-08-29T12:10:00+00:00",
            "phone": phone,
            "message_id": "wamid.appr.3",
            "message_type": "text",
            "message_text": "e a bomba de 2cv, qual o preço?",
        },
        trace_id="t-appr-3",
    )
    assert await process_event(third_env, outbound=outbound) is True
    assert "esta em analise" not in outbound.sent[-1]["text"].lower()
