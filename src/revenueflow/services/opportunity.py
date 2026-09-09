"""Opportunity Engine batch scan (SPEC-018, ADR-019, ADR-079).

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
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
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
    churn: int = 0
    reactivation: int = 0
    order_recovery: int = 0
    cross_sell: int = 0
    upsell: int = 0
    inventory_to_cash: int = 0
    created: int = 0
    errors: int = 0


async def _persist(conn: AsyncConnection[object], opp: Opportunity) -> bool:
    stored = await opportunity_repo.upsert_open(conn, opp)
    return stored.opportunity_id == opp.opportunity_id


async def _apply(
    conn: AsyncConnection[object],
    result: ScanResult,
    *,
    counter: str,
    candidates: Iterable[Any],
    rule: Callable[..., Opportunity | None],
    key: Callable[[Any], str],
    **rule_kwargs: Any,
) -> None:
    for signal in candidates:
        setattr(result, counter, getattr(result, counter) + 1)
        try:
            opp = rule(signal, **rule_kwargs)
            if opp is not None and await _persist(conn, opp):
                result.created += 1
        except Exception:
            result.errors += 1
            get_tracer().event("oppscan.candidate_failed", attrs={"type": counter})
            _LOGGER.exception("%s candidate failed: %s", counter, key(signal))


async def scan(*, now: datetime | None = None) -> ScanResult:
    settings = get_settings()
    moment = now or datetime.now(UTC)
    result = ScanResult()
    token = set_tracer(
        new_tracer(
            conversation_id="opportunity-scan",
            turn_id=f"oppscan-{uuid4().hex[:8]}",
        )
    )
    try:
        async with unit_of_work() as conn:
            replenishment_signals = await opportunity_repo.replenishment_candidates(conn)
            await _apply(
                conn,
                result,
                counter="replenishment",
                candidates=replenishment_signals,
                rule=opportunity_policy.replenishment,
                key=lambda s: s.customer_id,
                now=moment,
                threshold=Decimal(str(settings.replenishment_threshold)),
            )
            await _apply(
                conn,
                result,
                counter="churn",
                candidates=replenishment_signals,
                rule=opportunity_policy.churn,
                key=lambda s: s.customer_id,
                now=moment,
                threshold=Decimal(str(settings.churn_threshold)),
            )
            await _apply(
                conn,
                result,
                counter="reactivation",
                candidates=replenishment_signals,
                rule=opportunity_policy.reactivation,
                key=lambda s: s.customer_id,
                now=moment,
                threshold=Decimal(str(settings.reactivation_threshold)),
            )
            await _apply(
                conn,
                result,
                counter="quote_recovery",
                candidates=await opportunity_repo.stale_quote_candidates(conn),
                rule=opportunity_policy.quote_recovery,
                key=lambda s: s.quote_id,
                now=moment,
                limit_hours=settings.quote_recovery_hours,
            )
            await _apply(
                conn,
                result,
                counter="order_recovery",
                candidates=await opportunity_repo.order_recovery_candidates(conn),
                rule=opportunity_policy.order_recovery,
                key=lambda s: s.order_id,
                now=moment,
                min_age_hours=settings.order_recovery_hours,
            )
            await _apply(
                conn,
                result,
                counter="cross_sell",
                candidates=await opportunity_repo.cross_sell_candidates(conn),
                rule=opportunity_policy.cross_sell,
                key=lambda s: s.customer_id,
                now=moment,
            )
            await _apply(
                conn,
                result,
                counter="upsell",
                candidates=await opportunity_repo.upsell_candidates(conn),
                rule=opportunity_policy.upsell,
                key=lambda s: s.customer_id,
                now=moment,
                min_repeat_purchases=settings.upsell_min_repeat_purchases,
            )
            await _apply(
                conn,
                result,
                counter="inventory_to_cash",
                candidates=await opportunity_repo.inventory_to_cash_candidates(conn),
                rule=opportunity_policy.inventory_to_cash,
                key=lambda s: s.customer_id,
                now=moment,
                stock_threshold=settings.inventory_to_cash_stock_threshold,
                stale_days_threshold=settings.inventory_to_cash_stale_days,
            )
        get_tracer().event("oppscan.done", attrs=asdict(result))
        get_tracer().end(outcome="scanned")
        return result
    finally:
        await get_tracer().flush()
        reset_tracer(token)
