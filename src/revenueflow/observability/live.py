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

import psycopg

from revenueflow.config import get_settings
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
        # NOTIFY only reaches listeners once its transaction commits — a bare
        # pool connection (no explicit transaction) leaves it uncommitted,
        # rolled back on release, and silently never delivered. conn.transaction()
        # commits on clean exit (confirmed missing by a real CI failure: the
        # listener never received a payload, not a timeout from elsewhere).
        async with get_pool().connection() as conn, conn.transaction():
            await conn.execute("SELECT pg_notify(%s, %s)", (_CHANNEL, payload))
    except Exception:
        _LOGGER.warning("live agent-activity notify failed", exc_info=True)


async def listen() -> AsyncIterator[str]:
    """Yields raw JSON payload strings as they arrive. One dedicated LISTEN
    connection per caller (opened directly, NOT from the shared pool) —
    closed automatically when the generator exits (client disconnect).

    A pool connection is wrong here: repositories.db.get_pool() sets
    statement_timeout (ADR-057's turn latency budget) on every connection it
    hands out, which cancels conn.notifies()'s indefinite wait after a few
    seconds — confirmed by a real CI failure, not a hypothetical. A plain
    connection with no statement_timeout, outside the pool, also keeps a
    long-lived LISTEN from competing with the pool used for turn processing.
    """
    async with await psycopg.AsyncConnection.connect(get_settings().database_url) as conn:
        # Required: without autocommit, LISTEN leaves the connection
        # idle-in-transaction, and psycopg does not surface async NOTIFY
        # payloads while a transaction is open (confirmed by a real,
        # reproducible local failure — LISTEN registered, matching NOTIFYs
        # committed on the sender's side, never received here without this).
        await conn.set_autocommit(True)
        await conn.execute(f"LISTEN {_CHANNEL}")
        async for notify in conn.notifies():
            yield notify.payload
