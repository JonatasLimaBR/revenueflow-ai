"""Live agent-activity channel (ADR-073). Best-effort Postgres NOTIFY fired
from AuditTracer.span() (never blocks a turn — failures are swallowed and
logged); a LISTEN generator feeds the portal's SSE endpoint. No PII in the
payload (conversation_id is opaque, agent is a fixed node name)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from revenueflow.repositories.db import get_pool

_LOGGER = logging.getLogger(__name__)
_CHANNEL = "revenueflow_agent_activity"


def notify_agent_start(*, conversation_id: str, agent: str) -> None:
    _fire(conversation_id=conversation_id, agent=agent, status="started")


def notify_agent_end(*, conversation_id: str, agent: str) -> None:
    _fire(conversation_id=conversation_id, agent=agent, status="finished")


def _fire(*, conversation_id: str, agent: str, status: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no running loop (e.g. sync test context) — best-effort, skip
    loop.create_task(_notify(conversation_id=conversation_id, agent=agent, status=status))


async def _notify(*, conversation_id: str, agent: str, status: str) -> None:
    payload = json.dumps(
        {"conversation_id": conversation_id, "agent": agent, "status": status, "ts": time.time()}
    )
    try:
        async with get_pool().connection() as conn:
            await conn.execute("SELECT pg_notify(%s, %s)", (_CHANNEL, payload))
    except Exception:
        _LOGGER.warning("live agent-activity notify failed", exc_info=True)


async def listen() -> AsyncIterator[str]:
    """Yields raw JSON payload strings as they arrive. One dedicated LISTEN
    connection per caller — closed automatically when the generator exits
    (client disconnect)."""
    async with get_pool().connection() as conn:
        await conn.execute(f"LISTEN {_CHANNEL}")
        async for notify in conn.notifies():
            yield notify.payload
