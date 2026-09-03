"""Deterministic opportunity-detection rules (SPEC-018/019/020, ADR-019).

Each rule is a pure function: no I/O, no ``datetime.now()`` (the caller passes
``now``), no LLM. Given a signal, it returns an :class:`Opportunity` with a
human ``reason`` and a structured ``evidence`` (SPEC-021), or ``None`` when the
condition does not hold. ``probability`` is a documented per-type placeholder
until there is history to calibrate (ADR-018).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from revenueflow.domain.models import Opportunity, OpportunityStatus, OpportunityType

_REPLENISHMENT_PROBABILITY = Decimal("0.35")
_QUOTE_RECOVERY_PROBABILITY = Decimal("0.45")


@dataclass(slots=True)
class ReplenishmentSignal:
    customer_id: str
    product_id: str | None
    days_since_last_purchase: float
    average_purchase_interval: float
    average_ticket: Decimal


@dataclass(slots=True)
class QuoteRecoverySignal:
    quote_id: str
    customer_id: str
    product_id: str | None
    status: str
    created_at: datetime
    total: Decimal
    has_order: bool


def _opportunity(**fields: Any) -> Opportunity:
    return Opportunity(
        opportunity_id=uuid4().hex,
        status=OpportunityStatus.OPEN,
        **fields,
    )


def replenishment(
    signal: ReplenishmentSignal, *, now: datetime, threshold: Decimal
) -> Opportunity | None:
    limit = signal.average_purchase_interval * float(threshold)
    if signal.days_since_last_purchase <= limit:
        return None
    evidence = {
        "days_since_last_purchase": signal.days_since_last_purchase,
        "average_purchase_interval": signal.average_purchase_interval,
        "threshold": float(threshold),
    }
    reason = (
        f"Ultima compra ha {signal.days_since_last_purchase:.0f} dias; "
        f"intervalo medio {signal.average_purchase_interval:.0f} dias; "
        f"limite {float(threshold):g}x"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.REPLENISHMENT,
        product=signal.product_id,
        estimated_revenue=signal.average_ticket,
        probability=_REPLENISHMENT_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="offer_replenishment",
        created_at=now,
    )


def quote_recovery(
    signal: QuoteRecoverySignal, *, now: datetime, limit_hours: int
) -> Opportunity | None:
    age = now - signal.created_at
    if signal.status != "SENT" or signal.has_order or age <= timedelta(hours=limit_hours):
        return None
    age_hours = age.total_seconds() / 3600
    evidence = {
        "quote_id": signal.quote_id,
        "age_hours": age_hours,
        "limit_hours": limit_hours,
    }
    reason = (
        f"Proposta {signal.quote_id} enviada ha {age_hours:.0f}h sem pedido (limite {limit_hours}h)"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.QUOTE_RECOVERY,
        product=signal.product_id,
        estimated_revenue=signal.total,
        probability=_QUOTE_RECOVERY_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="follow_up_quote",
        created_at=now,
    )
