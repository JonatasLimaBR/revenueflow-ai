"""Human-handoff persistence (SPEC-026/027).

``create`` enforces "one PENDING handoff per conversation" via the partial
unique index from ``0008`` (``INSERT ... ON CONFLICT DO NOTHING`` + read-back).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from revenueflow.domain.models import Handoff, HandoffReason, HandoffStatus
from revenueflow.repositories.db import execute, fetchall, fetchone

_INSERT = """
INSERT INTO handoff (handoff_id, conversation_id, reason, context, status)
VALUES (%s, %s, %s, %s, 'PENDING')
ON CONFLICT (conversation_id) WHERE status = 'PENDING' DO NOTHING
"""

_SELECT_OPEN = """
SELECT handoff_id, conversation_id, reason, context, status, created_at
FROM handoff
WHERE conversation_id = %s AND status = 'PENDING'
"""

_SELECT_BY_STATUS = """
SELECT handoff_id, conversation_id, reason, context, status, created_at
FROM handoff
WHERE status = %s
ORDER BY created_at DESC
"""

_RESOLVE = "UPDATE handoff SET status = 'RESOLVED' WHERE handoff_id = %s AND status = 'PENDING'"


def _to_handoff(row: dict[str, Any]) -> Handoff:
    return Handoff(
        handoff_id=row["handoff_id"],
        conversation_id=row["conversation_id"],
        reason=HandoffReason(row["reason"]),
        context=row["context"],
        status=HandoffStatus(row["status"]),
        created_at=row["created_at"],
    )


async def create(
    conn: AsyncConnection[Any],
    conversation_id: str,
    reason: HandoffReason,
    context: dict[str, Any],
) -> Handoff:
    await execute(
        conn,
        _INSERT,
        (uuid4().hex, conversation_id, reason.value, Jsonb(context)),
    )
    row = await fetchone(conn, _SELECT_OPEN, (conversation_id,))
    if row is not None:
        return _to_handoff(row)
    raise RuntimeError(f"handoff missing immediately after create for {conversation_id}")


async def list_by_status(conn: AsyncConnection[Any], status: HandoffStatus) -> list[Handoff]:
    rows = await fetchall(conn, _SELECT_BY_STATUS, (status.value,))
    return [_to_handoff(row) for row in rows]


async def resolve(conn: AsyncConnection[Any], handoff_id: str) -> int:
    return await execute(conn, _RESOLVE, (handoff_id,))
