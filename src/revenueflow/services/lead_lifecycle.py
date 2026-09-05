"""Lead-status advancement and lead-to-customer promotion (ADR-062).

``advance_from_turn`` runs synchronously after a completed turn — cheap, no
external I/O beyond the OLTP already in scope. ``sweep_stale`` is a batch job,
outside the graph, same shape as ``services.opportunity.scan``: leads with no
recent activity move to ``LOST``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.config import get_settings
from revenueflow.domain.models import Customer, Intent, LeadStatus
from revenueflow.policies import lead_policy
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories.db import unit_of_work

_LOGGER = logging.getLogger(__name__)


async def advance_from_turn(*, lead_id: str | None, intent: str, final_outcome: str | None) -> None:
    if lead_id is None:
        return
    async with unit_of_work() as conn:
        lead = await lead_repo.get_by_id(conn, lead_id)
        if lead is None:
            return
        target = lead_policy.advance(
            lead.status, intent=Intent(intent), final_outcome=final_outcome
        )
        promote = target == LeadStatus.WON and lead.status != LeadStatus.WON
        if target != lead.status:
            await lead_repo.set_status(conn, lead_id, target)
        if promote:
            try:
                await customer_repo.create(
                    conn,
                    Customer(
                        customer_id=uuid4().hex,
                        phone=lead.phone,
                        name=None,
                        segment=None,
                        created_at=datetime.now(UTC),
                    ),
                )
            except Exception:
                _LOGGER.exception("lead-to-customer promotion failed: %s", lead_id)


@dataclass(slots=True)
class SweepResult:
    swept: int = 0


async def sweep_stale() -> SweepResult:
    settings = get_settings()
    result = SweepResult()
    async with unit_of_work() as conn:
        candidates = await lead_repo.stale_candidates(
            conn, stale_after_days=settings.lead_stale_days
        )
        for lead in candidates:
            await lead_repo.set_status(conn, lead.lead_id, LeadStatus.LOST)
            result.swept += 1
    return result
