from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.domain.models import Customer
from revenueflow.events import EventEnvelope, make_envelope
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.worker import get_graph, process_event, set_graph
from revenueflow.worker.consume import _OPT_OUT_CONFIRMED


@pytest.fixture
def outbound() -> Iterator[FakeOutbound]:
    set_graph(build_graph(MemorySaver()))
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        yield fake
    finally:
        reset_outbound(token)


@pytest.fixture
def graph_spy(outbound: FakeOutbound, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("graph.ainvoke should not run for an opt-out message")

    monkeypatch.setattr(get_graph(), "ainvoke", _boom)


async def _create_customer(phone: str) -> str:
    customer_id = f"CUST-OPT-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await customer_repo.create(
            conn,
            Customer(
                customer_id=customer_id,
                phone=phone,
                name="Opt Out Test",
                segment=None,
                created_at=datetime.now(UTC),
            ),
        )
    return customer_id


def _envelope(phone: str, text: str, event_id: str) -> EventEnvelope:
    return make_envelope(
        "message_received",
        {
            "event_id": event_id,
            "occurred_at": "2026-09-04T12:00:00+00:00",
            "phone": phone,
            "message_id": f"wamid.{event_id}",
            "message_type": "text",
            "message_text": text,
        },
        trace_id=event_id,
    )


@pytest.mark.parametrize("text", ["PARAR", " Parar ", "parar", "SAIR"])
async def test_opt_out_persists_and_replies_without_graph(
    text: str, db: None, graph_spy: None, outbound: FakeOutbound
) -> None:
    phone = f"+5511{uuid4().hex[:9]}"
    customer_id = await _create_customer(phone)

    env = _envelope(phone, text, f"e-opt-{uuid4().hex[:8]}")
    assert await process_event(env, outbound=outbound) is True

    assert len(outbound.sent) == 1
    assert outbound.sent[0]["text"] == _OPT_OUT_CONFIRMED

    async with unit_of_work() as conn:
        stored = await customer_repo.get_by_id(conn, customer_id)
    assert stored is not None
    assert stored.consent_opt_out_at is not None


async def test_opt_out_false_positive_runs_graph_normally(db: None, outbound: FakeOutbound) -> None:
    phone = f"+5511{uuid4().hex[:9]}"
    env = _envelope(phone, "Voce pode parar de me mandar boleto errado?", f"e-fp-{uuid4().hex[:8]}")

    assert await process_event(env, outbound=outbound) is True

    assert len(outbound.sent) == 1
    assert outbound.sent[0]["text"] != _OPT_OUT_CONFIRMED


async def test_opt_out_unknown_lead_no_customer_update(
    db: None, graph_spy: None, outbound: FakeOutbound
) -> None:
    phone = f"+5511{uuid4().hex[:9]}"
    env = _envelope(phone, "sair", f"e-lead-{uuid4().hex[:8]}")

    assert await process_event(env, outbound=outbound) is True

    assert len(outbound.sent) == 1
    assert outbound.sent[0]["text"] == _OPT_OUT_CONFIRMED

    async with unit_of_work() as conn:
        stored = await customer_repo.get_by_phone(conn, phone)
    assert stored is None
