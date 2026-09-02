from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.repositories.db import execute, fetchall, fetchone

_COLUMNS = (
    "approval_id, conversation_id, turn_id, reason, requested_discount, "
    "current_margin, resulting_margin, amount, customer_ref, status, "
    "expires_at, approved_discount, decided_at"
)

_INSERT = """
INSERT INTO approval (
    approval_id, conversation_id, turn_id, reason, requested_discount,
    current_margin, resulting_margin, amount, customer_ref, status, expires_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (conversation_id, turn_id) DO NOTHING
"""

_GET_BY_TURN = f"""
SELECT {_COLUMNS} FROM approval WHERE conversation_id = %s AND turn_id = %s
"""

_GET = f"SELECT {_COLUMNS} FROM approval WHERE approval_id = %s"

_LIST_BY_STATUS = f"""
SELECT {_COLUMNS} FROM approval WHERE status = %s ORDER BY created_at
"""

_TRANSITION = """
UPDATE approval
   SET status = %s, approved_discount = %s, decided_at = now()
 WHERE approval_id = %s AND status = 'PENDING'
"""


def _to_approval(row: dict[str, Any]) -> Approval:
    return Approval(
        approval_id=row["approval_id"],
        conversation_id=row["conversation_id"],
        turn_id=row["turn_id"],
        reason=row["reason"],
        requested_discount=row["requested_discount"],
        current_margin=row["current_margin"],
        resulting_margin=row["resulting_margin"],
        amount=row["amount"],
        customer_ref=row["customer_ref"],
        status=ApprovalStatus(row["status"]),
        expires_at=row["expires_at"],
        approved_discount=row["approved_discount"],
        decided_at=row["decided_at"],
    )


async def create_pending(conn: AsyncConnection[Any], approval: Approval) -> bool:
    rowcount = await execute(
        conn,
        _INSERT,
        (
            approval.approval_id,
            approval.conversation_id,
            approval.turn_id,
            approval.reason,
            approval.requested_discount,
            approval.current_margin,
            approval.resulting_margin,
            approval.amount,
            approval.customer_ref,
            approval.status.value,
            approval.expires_at,
        ),
    )
    return rowcount == 1


async def get(conn: AsyncConnection[Any], approval_id: str) -> Approval | None:
    row = await fetchone(conn, _GET, (approval_id,))
    return _to_approval(row) if row is not None else None


async def get_by_turn(
    conn: AsyncConnection[Any], conversation_id: str, turn_id: str
) -> Approval | None:
    row = await fetchone(conn, _GET_BY_TURN, (conversation_id, turn_id))
    return _to_approval(row) if row is not None else None


async def list_by_status(conn: AsyncConnection[Any], status: ApprovalStatus) -> list[Approval]:
    rows = await fetchall(conn, _LIST_BY_STATUS, (status.value,))
    return [_to_approval(row) for row in rows]


async def transition(
    conn: AsyncConnection[Any],
    approval_id: str,
    status: ApprovalStatus,
    approved_discount: Decimal | None,
) -> bool:
    rowcount = await execute(conn, _TRANSITION, (status.value, approved_discount, approval_id))
    return rowcount == 1
