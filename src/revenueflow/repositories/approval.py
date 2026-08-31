from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.repositories.db import execute, fetchone

_INSERT = """
INSERT INTO approval (
    approval_id, conversation_id, turn_id, reason, requested_discount,
    current_margin, resulting_margin, amount, customer_ref, status
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (conversation_id, turn_id) DO NOTHING
"""

_GET_BY_TURN = """
SELECT approval_id, conversation_id, turn_id, reason, requested_discount,
       current_margin, resulting_margin, amount, customer_ref, status
FROM approval
WHERE conversation_id = %s AND turn_id = %s
"""


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
        ),
    )
    return rowcount == 1


async def get_by_turn(
    conn: AsyncConnection[Any], conversation_id: str, turn_id: str
) -> Approval | None:
    row = await fetchone(conn, _GET_BY_TURN, (conversation_id, turn_id))
    if row is None:
        return None
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
    )
