from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from revenueflow.domain.models import MarginBreakdown, PriceQuote
from revenueflow.repositories import sim_catalog, sim_pricing
from revenueflow.repositories.db import read_connection

_VALID_DAYS = 7
_ZERO = Decimal("0")
_ONE = Decimal("1")
_CENT = Decimal("0.01")
_RATIO = Decimal("0.0001")


def _tier_price(price_tiers: list[dict[str, Any]], quantity: int) -> Decimal:
    best = _ZERO
    for tier in sorted(price_tiers, key=lambda t: int(t["min_qty"])):
        if quantity >= int(tier["min_qty"]):
            best = Decimal(str(tier["unit_price"]))
    return best


async def get_price(customer_ref: str | None, product_id: str, quantity: int) -> PriceQuote:
    async with read_connection() as conn:
        product = await sim_catalog.get(conn, product_id)
        if product is None:
            raise LookupError(product_id)
        cost = await sim_pricing.product_cost(conn, product_id)
        contract = (
            await sim_pricing.customer_pricing(conn, customer_ref, product_id)
            if customer_ref is not None
            else None
        )

    list_price = _tier_price(product["price_tiers"], quantity)
    customer_price = (
        Decimal(str(contract["negotiated_price"])) if contract is not None else list_price
    )
    maximum_discount = Decimal(str(contract["max_discount_pct"])) if contract is not None else None
    return PriceQuote(
        product_id=product_id,
        list_price=list_price,
        customer_price=customer_price,
        unit_cost=Decimal(str(cost["unit_cost"])),
        maximum_discount=maximum_discount,
        minimum_margin=Decimal(str(cost["min_margin_pct"])),
        valid_until=(datetime.now(UTC) + timedelta(days=_VALID_DAYS)).date(),
    )


def calculate_margin(price: Decimal, unit_cost: Decimal, discount: Decimal) -> MarginBreakdown:
    revenue = (price * (_ONE - discount)).quantize(_CENT)
    cost = unit_cost.quantize(_CENT)
    gross_profit = (revenue - cost).quantize(_CENT)
    margin = (gross_profit / revenue) if revenue > _ZERO else _ZERO
    return MarginBreakdown(
        revenue=revenue,
        cost=cost,
        gross_profit=gross_profit,
        margin=margin.quantize(_RATIO),
    )
