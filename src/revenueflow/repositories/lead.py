from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import Lead, LeadStatus
from revenueflow.repositories.db import execute, fetchall, fetchone

_SELECT_BY_PHONE = "SELECT lead_id, phone, status, created_at FROM lead WHERE phone = %s"

_SELECT_BY_ID = "SELECT lead_id, phone, status, created_at FROM lead WHERE lead_id = %s"

_INSERT = """
INSERT INTO lead (lead_id, phone, status, created_at)
VALUES (%s, %s, %s, %s)
ON CONFLICT (phone) DO NOTHING
"""

_SET_STATUS = "UPDATE lead SET status = %s WHERE lead_id = %s"

_STALE_CANDIDATES = """
SELECT l.lead_id, l.phone, l.status, l.created_at
FROM lead l
LEFT JOIN conversation_session cs ON cs.phone = l.phone
WHERE l.status NOT IN ('WON', 'LOST')
GROUP BY l.lead_id, l.phone, l.status, l.created_at
HAVING coalesce(max(cs.last_interaction), l.created_at) < now() - (%s || ' days')::interval
"""


def _to_lead(row: dict[str, Any]) -> Lead:
    return Lead(
        lead_id=row["lead_id"],
        phone=row["phone"],
        status=LeadStatus(row["status"]),
        created_at=row["created_at"],
    )


async def get_by_phone(conn: AsyncConnection[Any], phone: str) -> Lead | None:
    row = await fetchone(conn, _SELECT_BY_PHONE, (phone,))
    return _to_lead(row) if row is not None else None


async def create(conn: AsyncConnection[Any], lead: Lead) -> None:
    await execute(
        conn,
        _INSERT,
        (lead.lead_id, lead.phone, lead.status.value, lead.created_at),
    )


async def get_by_id(conn: AsyncConnection[Any], lead_id: str) -> Lead | None:
    row = await fetchone(conn, _SELECT_BY_ID, (lead_id,))
    return _to_lead(row) if row is not None else None


async def set_status(conn: AsyncConnection[Any], lead_id: str, status: LeadStatus) -> None:
    await execute(conn, _SET_STATUS, (status.value, lead_id))


async def stale_candidates(conn: AsyncConnection[Any], *, stale_after_days: int) -> list[Lead]:
    rows = await fetchall(conn, _STALE_CANDIDATES, (stale_after_days,))
    return [_to_lead(row) for row in rows]
