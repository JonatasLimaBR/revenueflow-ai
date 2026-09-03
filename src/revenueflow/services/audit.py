"""Audit-trail orchestration (SPEC-028, ADR-055).

``persist`` writes one ``audit_event`` and **never raises**: a failure here must
not break the turn (the customer reply has already been sent). ``reconstruct``
returns a conversation's turns for the internal reconstruction route.
"""

from __future__ import annotations

import logging
from typing import Any

from revenueflow.domain.models import AuditEvent
from revenueflow.repositories import audit as audit_repo
from revenueflow.repositories.db import read_connection, unit_of_work

_LOGGER = logging.getLogger(__name__)


async def persist(event: AuditEvent) -> None:
    try:
        async with unit_of_work() as conn:
            await audit_repo.record(conn, event)
    except Exception:
        _LOGGER.exception("audit persist failed for %s", event.trace_id)


async def reconstruct(conversation_id: str) -> list[dict[str, Any]]:
    async with read_connection() as conn:
        rows = await audit_repo.by_conversation(conn, conversation_id)
    return [
        {
            "audit_id": row.audit_id,
            "trace_id": row.trace_id,
            "turn_id": row.turn_id,
            "agent": row.agent,
            "model": row.model,
            "outcome": row.outcome,
            "token_usage": row.token_usage,
            "cost_usd": str(row.cost_usd),
            "latency_ms": row.latency_ms,
            "events": row.events,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
