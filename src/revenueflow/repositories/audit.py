"""Audit-trail persistence (SPEC-028).

One ``audit_event`` row per turn, keyed by ``audit_id = turn_id`` so a
re-processed turn cannot double-write (``ON CONFLICT DO NOTHING``).
``by_conversation`` returns the rows for a conversation in time order for
reconstruction (PRD-013).
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from revenueflow.domain.models import AuditEvent
from revenueflow.repositories.db import execute, fetchall

_COLUMNS = (
    "audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version, "
    "outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, "
    "events, created_at"
)

_INSERT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (audit_id) DO NOTHING
"""

_BY_CONVERSATION = (
    f"SELECT {_COLUMNS} FROM audit_event WHERE conversation_id = %s ORDER BY created_at"
)


def _to_audit_event(row: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        audit_id=row["audit_id"],
        trace_id=row["trace_id"],
        conversation_id=row["conversation_id"],
        turn_id=row["turn_id"],
        agent=row["agent"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        outcome=row["outcome"],
        policy_decision=row["policy_decision"],
        handoff=row["handoff"],
        tools=row["tools"],
        token_usage=row["token_usage"],
        cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"],
        events=row["events"],
        created_at=row["created_at"],
    )


async def record(conn: AsyncConnection[Any], event: AuditEvent) -> None:
    await execute(
        conn,
        _INSERT,
        (
            event.audit_id,
            event.trace_id,
            event.conversation_id,
            event.turn_id,
            event.agent,
            event.model,
            event.prompt_version,
            event.outcome,
            event.policy_decision,
            event.handoff,
            Jsonb(event.tools),
            event.token_usage,
            event.cost_usd,
            event.latency_ms,
            Jsonb(event.events),
        ),
    )


async def by_conversation(conn: AsyncConnection[Any], conversation_id: str) -> list[AuditEvent]:
    rows = await fetchall(conn, _BY_CONVERSATION, (conversation_id,))
    return [_to_audit_event(row) for row in rows]
