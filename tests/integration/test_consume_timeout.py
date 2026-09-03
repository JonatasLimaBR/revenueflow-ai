import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.config import get_settings
from revenueflow.events import make_envelope
from revenueflow.repositories.db import fetchone, read_connection
from revenueflow.services import get_or_create
from revenueflow.worker import process_approval_decided, process_event, set_graph
from revenueflow.worker.consume import _SLOW_REPLY

_PHONE = "+5511977777777"


class _SlowState:
    next: tuple[str, ...] = ()


class _SlowGraph:
    async def aget_state(self, _config: Any) -> _SlowState:
        return _SlowState()

    async def ainvoke(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
        await asyncio.sleep(5)
        return {"reply": "never", "intent": "product_search"}


@pytest.fixture
def slow_turn(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeOutbound]:
    monkeypatch.setenv("TURN_BUDGET_S", "0.2")
    get_settings.cache_clear()
    set_graph(_SlowGraph())
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        yield fake
    finally:
        reset_outbound(token)
        get_settings.cache_clear()


def _envelope(event_id: str) -> Any:
    return make_envelope(
        "message_received",
        {
            "phone": _PHONE,
            "message_text": "quanto custa a bomba",
            "message_id": f"wamid.{event_id}",
        },
        trace_id=f"t-{event_id}",
    )


async def test_turn_budget_exceeded_sends_slow_reply_and_acks(
    db: None, slow_turn: FakeOutbound
) -> None:
    env = _envelope("TO1")

    assert await process_event(env, outbound=slow_turn) is True

    assert len(slow_turn.sent) == 1
    assert slow_turn.sent[0]["text"] == _SLOW_REPLY

    session = await get_or_create(_PHONE)
    async with read_connection() as conn:
        row = await fetchone(
            conn,
            "SELECT outcome FROM audit_event WHERE conversation_id = %s",
            (session.conversation_id,),
        )
    assert row is not None
    assert row["outcome"] == "timeout"


async def test_timed_out_event_is_not_reprocessed(db: None, slow_turn: FakeOutbound) -> None:
    env = _envelope("TO2")

    assert await process_event(env, outbound=slow_turn) is True
    assert await process_event(env, outbound=slow_turn) is False
    assert len(slow_turn.sent) == 1


async def test_resume_turn_budget_exceeded_sends_slow_reply(
    db: None, slow_turn: FakeOutbound
) -> None:
    session = await get_or_create(_PHONE)
    env = make_envelope(
        "approval_decided",
        {"conversation_id": session.conversation_id, "decision": "approved", "discount_pct": 12.0},
        trace_id="t-resume-to",
    )

    assert await process_approval_decided(env, outbound=slow_turn) is True
    assert len(slow_turn.sent) == 1
    assert slow_turn.sent[0]["text"] == _SLOW_REPLY
