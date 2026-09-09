"""Expiration sweep for stale Approvals, Quotes and Handoffs.

Runs as a batch job, outside the graph and outside the request path (same
shape as ``services.opportunity.scan``/``services.lead_lifecycle.sweep_stale``,
ADR-019/020). Nothing here is a new UX decision: each entity already has a
deterministic "what happens when nobody decides in time" fallback --

- ``Approval``: ``apply_decision_node`` (agents/apply_decision.py) already
  re-derives "expired" itself from ``expires_at`` whenever the paused turn
  finally resumes. The gap this closes is that nothing ever nudged that
  resume to happen on its own -- an Approval nobody ever decided left the
  LangGraph checkpoint paused in ``await_approval`` forever, and every
  message on that conversation kept hitting the fixed "still under review"
  reply (found live, 2026-09-09). Publishing ``approval_decided`` here is the
  exact same event the human-decision API route publishes (services/approval.py).
- ``Quote``: past its ``expiration``, it stops being returned by
  ``get_open_quote`` (status != 'SENT') -- the customer's next message falls
  through to a normal turn instead of an eternal "responda 'sim, pode
  fechar'" against stale pricing.
- ``Handoff``: nobody on the team ever resolved it. Auto-resolving and
  handing the conversation back to the graph is the same "don't leave the
  customer stuck forever" call already made for Approval/Quote above --
  this only ever fires after `handoff_stale_hours` of total silence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from revenueflow.config import get_settings
from revenueflow.domain.models import SessionStatus
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import approval as approval_service


@dataclass(slots=True)
class SweepResult:
    approvals_expired: int = 0
    quotes_expired: int = 0
    handoffs_expired: int = 0


async def sweep(*, now: datetime | None = None) -> SweepResult:
    at = now or datetime.now(UTC)
    settings = get_settings()
    result = SweepResult()

    async with unit_of_work() as conn:
        stale_approvals = await approval_repo.list_expired_pending(conn, at)
    for approval in stale_approvals:
        decision = await approval_service.decide(approval.approval_id, "expire", None)
        if decision["published"]:
            result.approvals_expired += 1

    async with unit_of_work() as conn:
        result.quotes_expired = await checkout_repo.expire_stale_quotes(conn, at)

    stale_after = at - timedelta(hours=settings.handoff_stale_hours)
    async with unit_of_work() as conn:
        stale_handoffs = await handoff_repo.list_stale_pending(conn, stale_after)
        for pending in stale_handoffs:
            conversation_id = await handoff_repo.resolve(conn, pending.handoff_id)
            if conversation_id is not None:
                await session_repo.update_status(conn, conversation_id, SessionStatus.OPEN)
                result.handoffs_expired += 1

    return result
