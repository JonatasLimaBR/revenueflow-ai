from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import make_envelope
from revenueflow.repositories.db import fetchall, fetchone, read_connection
from revenueflow.services.opportunity import scan
from revenueflow.worker import process_event, set_graph


@pytest.fixture
def outbound() -> Iterator[FakeOutbound]:
    set_graph(build_graph(MemorySaver()))
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        yield fake
    finally:
        reset_outbound(token)


def _envelope(text: str) -> Any:
    return make_envelope(
        "message_received",
        {
            "event_id": f"e-{uuid4().hex}",
            "occurred_at": "2026-09-03T12:00:00+00:00",
            "phone": f"+5511{uuid4().hex[:9]}",
            "message_id": f"wamid.{uuid4().hex}",
            "message_type": "text",
            "message_text": text,
        },
        trace_id=f"t-{uuid4().hex}",
    )


async def test_process_event_writes_one_audit_row(db: None, outbound: FakeOutbound) -> None:
    env = _envelope("quero uma bomba d'agua 1cv")
    assert await process_event(env, outbound=outbound) is True

    async with read_connection() as conn:
        row = await fetchone(
            conn,
            "SELECT outcome, tools, events, agent FROM audit_event WHERE audit_id = %s",
            (env.event_id,),
        )
    assert row is not None
    assert row["outcome"]
    assert "tool.search_products" in row["tools"]
    assert row["events"]


async def test_scan_writes_one_audit_row(db: None) -> None:
    await scan()

    async with read_connection() as conn:
        rows = await fetchall(
            conn,
            "SELECT outcome FROM audit_event WHERE conversation_id = 'opportunity-scan' "
            "ORDER BY created_at DESC LIMIT 1",
        )
    assert rows
    assert rows[0]["outcome"] == "scanned"


async def test_error_turn_is_still_audited(
    db: None, outbound: FakeOutbound, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("graph blew up")

    from revenueflow.worker import consume as consume_module

    class _BoomGraph:
        async def aget_state(self, _config: Any) -> Any:
            class _S:
                next: tuple[str, ...] = ()

            return _S()

        async def ainvoke(self, *_a: object, **_k: object) -> Any:
            raise RuntimeError("graph blew up")

    monkeypatch.setattr(consume_module, "get_graph", lambda: _BoomGraph())

    env = _envelope("qualquer coisa")
    with pytest.raises(RuntimeError):
        await process_event(env, outbound=outbound)

    async with read_connection() as conn:
        row = await fetchone(
            conn, "SELECT outcome FROM audit_event WHERE audit_id = %s", (env.event_id,)
        )
    assert row is not None
    assert row["outcome"] == "error"
