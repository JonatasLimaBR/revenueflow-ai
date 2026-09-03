"""Opportunity Engine batch scan (SPEC-018, ADR-019).

``scan`` runs outside the LangGraph turn and the ``process_event`` consumer: it
pulls candidate signals, applies the pure rules from
:mod:`revenueflow.policies.opportunity_policy`, and upserts one OPEN
:class:`Opportunity` per firing signal. It never sends a message (SPEC-022) and
imports neither ``revenueflow.agents`` nor ``revenueflow.adapters``.

A failing candidate is logged with the run ``trace_id`` and counted in
``ScanResult.errors``; it does not abort the scan.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from psycopg import AsyncConnection

from revenueflow.config import get_settings
from revenueflow.domain.models import Opportunity
from revenueflow.observability import get_tracer, new_tracer, reset_tracer, set_tracer
from revenueflow.policies import opportunity_policy
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import unit_of_work

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScanResult:
    replenishment: int = 0
    quote_recovery: int = 0
    created: int = 0
    errors: int = 0


async def _persist(conn: AsyncConnection[object], opp: Opportunity) -> bool:
    stored = await opportunity_repo.upsert_open(conn, opp)
    return stored.opportunity_id == opp.opportunity_id


async def scan(*, now: datetime | None = None) -> ScanResult:
    settings = get_settings()
    moment = now or datetime.now(UTC)
    threshold = Decimal(str(settings.replenishment_threshold))
    limit_hours = settings.quote_recovery_hours
    result = ScanResult()
    token = set_tracer(
        new_tracer(
            conversation_id="opportunity-scan",
            turn_id=f"oppscan-{uuid4().hex[:8]}",
        )
    )
    try:
        async with unit_of_work() as conn:
            for signal in await opportunity_repo.replenishment_candidates(conn):
                result.replenishment += 1
                try:
                    opp = opportunity_policy.replenishment(signal, now=moment, threshold=threshold)
                    if opp is not None and await _persist(conn, opp):
                        result.created += 1
                except Exception:
                    result.errors += 1
                    get_tracer().event("oppscan.candidate_failed", attrs={"type": "replenishment"})
                    _LOGGER.exception("replenishment candidate failed: %s", signal.customer_id)
            for quote_signal in await opportunity_repo.stale_quote_candidates(conn):
                result.quote_recovery += 1
                try:
                    opp = opportunity_policy.quote_recovery(
                        quote_signal, now=moment, limit_hours=limit_hours
                    )
                    if opp is not None and await _persist(conn, opp):
                        result.created += 1
                except Exception:
                    result.errors += 1
                    get_tracer().event("oppscan.candidate_failed", attrs={"type": "quote_recovery"})
                    _LOGGER.exception("quote recovery candidate failed: %s", quote_signal.quote_id)
        get_tracer().event("oppscan.done", attrs=asdict(result))
        get_tracer().end(outcome="scanned")
        return result
    finally:
        reset_tracer(token)
