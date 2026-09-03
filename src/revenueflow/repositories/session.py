from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import ConversationSession, Intent, SessionStatus
from revenueflow.repositories.db import execute, fetchone

_COLUMNS = (
    "conversation_id, phone, status, current_intent, current_agent, "
    "last_interaction, customer_id, lead_id"
)

_SELECT_OPEN = f"""
SELECT {_COLUMNS}
FROM conversation_session
WHERE phone = %s AND status <> 'CLOSED'
ORDER BY last_interaction DESC
LIMIT 1
"""

_INSERT = f"""
INSERT INTO conversation_session ({_COLUMNS})
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

_UPDATE_STATUS = "UPDATE conversation_session SET status = %s WHERE conversation_id = %s"


def _to_session(row: dict[str, Any]) -> ConversationSession:
    current_intent = row["current_intent"]
    return ConversationSession(
        conversation_id=row["conversation_id"],
        phone=row["phone"],
        status=SessionStatus(row["status"]),
        last_interaction=row["last_interaction"],
        current_intent=Intent(current_intent) if current_intent is not None else None,
        current_agent=row["current_agent"],
        customer_id=row["customer_id"],
        lead_id=row["lead_id"],
    )


async def get_open_by_phone(conn: AsyncConnection[Any], phone: str) -> ConversationSession | None:
    row = await fetchone(conn, _SELECT_OPEN, (phone,))
    return _to_session(row) if row is not None else None


async def phone_for(conn: AsyncConnection[Any], conversation_id: str) -> str | None:
    row = await fetchone(
        conn,
        "SELECT phone FROM conversation_session WHERE conversation_id = %s",
        (conversation_id,),
    )
    return None if row is None else str(row["phone"])


async def create(conn: AsyncConnection[Any], session: ConversationSession) -> None:
    current_intent = session.current_intent.value if session.current_intent is not None else None
    await execute(
        conn,
        _INSERT,
        (
            session.conversation_id,
            session.phone,
            session.status.value,
            current_intent,
            session.current_agent,
            session.last_interaction,
            session.customer_id,
            session.lead_id,
        ),
    )


async def update_status(
    conn: AsyncConnection[Any], conversation_id: str, status: SessionStatus
) -> None:
    await execute(conn, _UPDATE_STATUS, (status.value, conversation_id))


async def set_customer(conn: AsyncConnection[Any], conversation_id: str, customer_id: str) -> None:
    await execute(
        conn,
        "UPDATE conversation_session SET customer_id = %s WHERE conversation_id = %s",
        (customer_id, conversation_id),
    )


async def touch(
    conn: AsyncConnection[Any],
    conversation_id: str,
    *,
    intent: Intent | None = None,
    agent: str | None = None,
) -> None:
    assignments = ["last_interaction = now()"]
    params: list[Any] = []
    if intent is not None:
        assignments.append("current_intent = %s")
        params.append(intent.value)
    if agent is not None:
        assignments.append("current_agent = %s")
        params.append(agent)
    params.append(conversation_id)
    sql = f"UPDATE conversation_session SET {', '.join(assignments)} WHERE conversation_id = %s"
    await execute(conn, sql, params)
