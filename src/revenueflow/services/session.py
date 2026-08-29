"""Conversation session service.

Thin orchestration over :mod:`revenueflow.repositories.session` (imported here as
``session_repo`` to avoid confusion with this module): it owns id generation and
the open-session lookup, and delegates every write to the repository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.domain.models import ConversationSession, Intent, SessionStatus
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import unit_of_work


async def get_or_create(phone: str) -> ConversationSession:
    """Return the open session for ``phone`` or create a fresh one."""

    async with unit_of_work() as conn:
        existing = await session_repo.get_open_by_phone(conn, phone)
        if existing is not None:
            return existing
        created = ConversationSession(
            conversation_id=uuid4().hex,
            phone=phone,
            status=SessionStatus.OPEN,
            last_interaction=datetime.now(UTC),
        )
        await session_repo.create(conn, created)
        return created


async def close(conversation_id: str) -> None:
    """Mark the session closed."""

    async with unit_of_work() as conn:
        await session_repo.update_status(conn, conversation_id, SessionStatus.CLOSED)


async def mark_waiting_customer(conversation_id: str) -> None:
    """Mark the session as waiting on the customer's next reply."""

    async with unit_of_work() as conn:
        await session_repo.update_status(conn, conversation_id, SessionStatus.WAITING_CUSTOMER)


async def record_turn(
    conversation_id: str,
    *,
    intent: Intent | None = None,
    agent: str | None = None,
) -> None:
    """Bump ``last_interaction`` and optionally the current intent and agent."""

    async with unit_of_work() as conn:
        await session_repo.touch(conn, conversation_id, intent=intent, agent=agent)
