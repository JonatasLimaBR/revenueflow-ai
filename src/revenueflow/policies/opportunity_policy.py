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
_CHURN_PROBABILITY = Decimal("0.25")
_REACTIVATION_PROBABILITY = Decimal("0.15")
_ORDER_RECOVERY_PROBABILITY = Decimal("0.40")
_CROSS_SELL_PROBABILITY = Decimal("0.20")
_UPSELL_PROBABILITY = Decimal("0.20")
_INVENTORY_TO_CASH_PROBABILITY = Decimal("0.15")


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


@dataclass(slots=True)
class OrderRecoverySignal:
    order_id: str
    customer_id: str
    product_id: str | None
    total: Decimal
    failed_at: datetime


@dataclass(slots=True)
class CrossSellSignal:
    customer_id: str
    complement_product_id: str
    complement_price: Decimal
    purchased_category: str


@dataclass(slots=True)
class UpsellSignal:
    customer_id: str
    current_product_id: str
    repeat_count: int
    upgrade_product_id: str
    upgrade_price: Decimal


@dataclass(slots=True)
class InventoryToCashSignal:
    customer_id: str
    product_id: str
    available: int
    stale_days: int
    unit_price: Decimal


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


def churn(signal: ReplenishmentSignal, *, now: datetime, threshold: Decimal) -> Opportunity | None:
    """Same signal as :func:`replenishment`, a higher (more severe) multiplier.

    ``product`` is intentionally ``None`` (ADR-079): this is a whole-relationship
    signal, not a single-product one, so it does not compete with a same-product
    REPLENISHMENT opportunity for the unique-open-per-signal index.
    """

    limit = signal.average_purchase_interval * float(threshold)
    if signal.days_since_last_purchase <= limit:
        return None
    evidence = {
        "days_since_last_purchase": signal.days_since_last_purchase,
        "average_purchase_interval": signal.average_purchase_interval,
        "threshold": float(threshold),
    }
    reason = (
        f"Sem comprar ha {signal.days_since_last_purchase:.0f} dias "
        f"({float(threshold):g}x o intervalo medio de {signal.average_purchase_interval:.0f} dias)"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.CHURN,
        product=None,
        estimated_revenue=signal.average_ticket,
        probability=_CHURN_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="reengagement_outreach",
        created_at=now,
    )


def reactivation(
    signal: ReplenishmentSignal, *, now: datetime, threshold: Decimal
) -> Opportunity | None:
    """The most severe tier of the same signal as :func:`churn` (ADR-079)."""

    limit = signal.average_purchase_interval * float(threshold)
    if signal.days_since_last_purchase <= limit:
        return None
    evidence = {
        "days_since_last_purchase": signal.days_since_last_purchase,
        "average_purchase_interval": signal.average_purchase_interval,
        "threshold": float(threshold),
    }
    reason = (
        f"Cliente dormente ha {signal.days_since_last_purchase:.0f} dias "
        f"({float(threshold):g}x o intervalo medio de {signal.average_purchase_interval:.0f} dias)"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.REACTIVATION,
        product=None,
        estimated_revenue=signal.average_ticket,
        probability=_REACTIVATION_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="win_back_campaign",
        created_at=now,
    )


def order_recovery(
    signal: OrderRecoverySignal, *, now: datetime, min_age_hours: int
) -> Opportunity | None:
    """A FAILED order (never retried into a paid one) old enough to follow up on."""

    age = now - signal.failed_at
    if age <= timedelta(hours=min_age_hours):
        return None
    age_hours = age.total_seconds() / 3600
    evidence = {
        "order_id": signal.order_id,
        "age_hours": age_hours,
        "min_age_hours": min_age_hours,
    }
    reason = f"Pedido {signal.order_id} falhou ha {age_hours:.0f}h e nunca foi refeito"
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.ORDER_RECOVERY,
        product=signal.product_id,
        estimated_revenue=signal.total,
        probability=_ORDER_RECOVERY_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="retry_payment_offer",
        created_at=now,
    )


def cross_sell(signal: CrossSellSignal, *, now: datetime) -> Opportunity:
    """A customer with confirmed purchases in a category but no accessory yet.

    Eligibility is entirely in the candidate query (ADR-079): unlike the other
    rules there is no numeric threshold to gate on here, so this always fires.
    """

    evidence = {
        "complement_product_id": signal.complement_product_id,
        "purchased_category": signal.purchased_category,
    }
    reason = (
        f"Comprou da categoria '{signal.purchased_category}' mas nunca levou "
        f"o acessorio {signal.complement_product_id}"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.CROSS_SELL,
        product=signal.complement_product_id,
        estimated_revenue=signal.complement_price,
        probability=_CROSS_SELL_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="offer_accessory",
        created_at=now,
    )


def upsell(signal: UpsellSignal, *, now: datetime, min_repeat_purchases: int) -> Opportunity | None:
    """A customer who repeat-bought a product is a candidate for the next tier up."""

    if signal.repeat_count < min_repeat_purchases:
        return None
    evidence = {
        "current_product_id": signal.current_product_id,
        "repeat_count": signal.repeat_count,
        "min_repeat_purchases": min_repeat_purchases,
    }
    reason = (
        f"Comprou {signal.current_product_id} {signal.repeat_count}x; "
        f"{signal.upgrade_product_id} e o proximo nivel da mesma categoria"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.UPSELL,
        product=signal.upgrade_product_id,
        estimated_revenue=signal.upgrade_price,
        probability=_UPSELL_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="offer_upgrade",
        created_at=now,
    )


def inventory_to_cash(
    signal: InventoryToCashSignal, *, now: datetime, stock_threshold: int, stale_days_threshold: int
) -> Opportunity | None:
    """High idle stock offered to a customer who already buys this category.

    Direction is reversed from every other rule (ADR-079): the signal starts
    from the product (excess inventory), not the customer.
    """

    if signal.available < stock_threshold or signal.stale_days < stale_days_threshold:
        return None
    evidence = {
        "available": signal.available,
        "stale_days": signal.stale_days,
        "stock_threshold": stock_threshold,
        "stale_days_threshold": stale_days_threshold,
    }
    reason = (
        f"{signal.available} unidades de {signal.product_id} paradas ha "
        f"{signal.stale_days} dias sem saida"
    )
    return _opportunity(
        customer_id=signal.customer_id,
        opportunity_type=OpportunityType.INVENTORY_TO_CASH,
        product=signal.product_id,
        estimated_revenue=signal.unit_price,
        probability=_INVENTORY_TO_CASH_PROBABILITY,
        reason=reason,
        evidence=evidence,
        recommended_action="offer_clearance",
        created_at=now,
    )
