"""Live agent-activity channel (ADR-073): a real NOTIFY/LISTEN round-trip
against Postgres (db-gated), plus a pure unit test proving a NOTIFY failure
never raises — the non-negotiable invariant since this runs inside the real
turn path (AuditTracer.span)."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import pytest

from revenueflow.observability import live


async def test_notify_and_listen_round_trip(db: None) -> None:
    async def _collect_one() -> str:
        async for payload in live.listen():
            return payload
        raise AssertionError("listen() ended without yielding a payload")

    listener_task = asyncio.ensure_future(_collect_one())

    # listen()'s connect() + LISTEN round-trip has real, variable latency (a
    # fresh connection per call — confirmed by a real failure locally and in
    # CI with a single fixed sleep before firing once). Retrying the notify
    # is safe (each is an independent, idempotent-for-this-purpose event) and
    # makes the test robust to that latency instead of guessing a bigger
    # magic number.
    async def _notify_until_received() -> None:
        while not listener_task.done():
            live.notify_agent_start(conversation_id="conv-live-test", agent="recommendation")
            await asyncio.sleep(0.3)

    notifier_task = asyncio.ensure_future(_notify_until_received())
    try:
        payload = await asyncio.wait_for(listener_task, timeout=5.0)
    finally:
        notifier_task.cancel()
    data = json.loads(payload)
    assert data["conversation_id"] == "conv-live-test"
    assert data["agent"] == "recommendation"
    assert data["status"] == "started"


async def test_notify_failure_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenPool:
        def connection(self) -> Any:
            @asynccontextmanager
            async def _ctx() -> Any:
                raise RuntimeError("pool unavailable")
                yield None  # pragma: no cover — unreachable, satisfies the generator shape

            return _ctx()

    monkeypatch.setattr(live, "get_pool", lambda: _BrokenPool())

    # must not raise, despite the broken pool
    await live._notify(conversation_id="conv-1", agent="checkout", status="started")


def test_fire_without_running_loop_is_a_noop() -> None:
    # notify_agent_start/_end call asyncio.get_running_loop(); outside of an
    # event loop this must be a silent no-op, never an exception.
    live.notify_agent_start(conversation_id="conv-1", agent="checkout")
    live.notify_agent_end(conversation_id="conv-1", agent="checkout")
