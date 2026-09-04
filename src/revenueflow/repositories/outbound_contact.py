from datetime import datetime
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection

from revenueflow.domain.models import CampaignContactStatus, CampaignSkipReason
from revenueflow.repositories.db import execute, fetchone

_LAST_CONTACT = """
SELECT max(contacted_at) AS last_at
FROM outbound_contact
WHERE customer_id = %s AND status = 'SENT'
"""

_INSERT = """
INSERT INTO outbound_contact (contact_id, customer_id, opportunity_id, status, skip_reason)
VALUES (%s, %s, %s, %s, %s)
"""


async def last_contact_at(conn: AsyncConnection[Any], customer_id: str) -> datetime | None:
    row = await fetchone(conn, _LAST_CONTACT, (customer_id,))
    return row["last_at"] if row is not None else None


async def record(
    conn: AsyncConnection[Any],
    *,
    customer_id: str,
    opportunity_id: str,
    status: CampaignContactStatus,
    skip_reason: CampaignSkipReason | None = None,
) -> None:
    await execute(
        conn,
        _INSERT,
        (
            uuid4().hex,
            customer_id,
            opportunity_id,
            status.value,
            skip_reason.value if skip_reason is not None else None,
        ),
    )
