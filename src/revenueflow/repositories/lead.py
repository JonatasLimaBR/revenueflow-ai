from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import Lead, LeadStatus
from revenueflow.repositories.db import execute, fetchone

_SELECT_BY_PHONE = "SELECT lead_id, phone, status, created_at FROM lead WHERE phone = %s"

_INSERT = """
INSERT INTO lead (lead_id, phone, status, created_at)
VALUES (%s, %s, %s, %s)
ON CONFLICT (phone) DO NOTHING
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
