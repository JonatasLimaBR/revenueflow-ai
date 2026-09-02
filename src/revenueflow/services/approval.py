"""Approval decision service.

``list_pending`` gives an operator the open approvals to act on; ``decide``
transitions one out of ``PENDING`` (conditionally, so a repeat is a no-op) and,
only when the transition actually happened, publishes an ``approval_decided``
event for the pull consumer to resume the paused turn.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from revenueflow.domain.errors import DomainError
from revenueflow.domain.models import ApprovalStatus
from revenueflow.events import get_publisher, make_envelope
from revenueflow.observability import get_tracer
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work

_TOPIC = "revenueflow.messages"

_DECISION_STATUS = {
    "approve": ApprovalStatus.APPROVED,
    "approve_with_override": ApprovalStatus.APPROVED,
    "reject": ApprovalStatus.REJECTED,
}


async def list_pending() -> list[dict[str, Any]]:
    """Return the open approvals an operator can decide, JSON-safe."""

    async with unit_of_work() as conn:
        rows = await approval_repo.list_by_status(conn, ApprovalStatus.PENDING)
    return [
        {
            "approval_id": row.approval_id,
            "conversation_id": row.conversation_id,
            "reason": row.reason,
            "requested_discount": str(row.requested_discount),
            "amount": str(row.amount),
            "customer_ref": row.customer_ref,
            "expires_at": row.expires_at.isoformat() if row.expires_at is not None else None,
        }
        for row in rows
    ]


async def decide(approval_id: str, decision: str, discount_pct: Decimal | None) -> dict[str, Any]:
    """Record the decision and, if it moved the row, publish ``approval_decided``."""

    async with unit_of_work() as conn:
        current = await approval_repo.get(conn, approval_id)
        if current is None:
            raise DomainError("approval not found")
        applied = discount_pct if decision == "approve_with_override" else None
        moved = await approval_repo.transition(
            conn, approval_id, _DECISION_STATUS[decision], applied
        )

    if not moved:
        return {"published": False, "status": current.status.value}

    envelope = make_envelope(
        "approval_decided",
        {
            "approval_id": approval_id,
            "conversation_id": current.conversation_id,
            "decision": decision,
            "discount_pct": str(discount_pct) if discount_pct is not None else None,
        },
        trace_id=get_tracer().trace_id,
    )
    await get_publisher().publish(_TOPIC, envelope)
    return {"published": True, "status": _DECISION_STATUS[decision].value}
