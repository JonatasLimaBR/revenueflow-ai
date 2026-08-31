"""Deterministic pricing tools for the Negotiation Agent (D5, SPEC-011/024/025).

Each callable is a thin traced wrapper over the deterministic pricing service
and policy. They never write and never let the model touch price, cost, or
margin: every number is computed by :mod:`revenueflow.services.pricing` and
:mod:`revenueflow.policies.pricing_policy`. Results are JSON-safe -- ``Decimal``
is rendered as ``str`` and ``date`` as an ISO string -- so the LangGraph state
they land in stays serializable for the Postgres checkpointer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from revenueflow.config import get_settings
from revenueflow.observability import get_tracer
from revenueflow.policies import pricing_policy
from revenueflow.services import pricing


async def get_price(customer_ref: str | None, product_id: str, quantity: int = 1) -> dict[str, Any]:
    """Return a JSON-safe price quote for ``product_id`` at ``quantity``."""

    with get_tracer().span("tool.get_price"):
        quote = await pricing.get_price(customer_ref, product_id, quantity)
    return {
        "product_id": quote.product_id,
        "list_price": str(quote.list_price),
        "customer_price": str(quote.customer_price),
        "unit_cost": str(quote.unit_cost),
        "maximum_discount": (
            None if quote.maximum_discount is None else str(quote.maximum_discount)
        ),
        "minimum_margin": str(quote.minimum_margin),
        "valid_until": quote.valid_until.isoformat(),
    }


async def calculate_margin(price: str, unit_cost: str, discount: str) -> dict[str, Any]:
    """Return a JSON-safe margin breakdown for the given price and discount."""

    with get_tracer().span("tool.calculate_margin"):
        breakdown = pricing.calculate_margin(Decimal(price), Decimal(unit_cost), Decimal(discount))
    return {
        "revenue": str(breakdown.revenue),
        "cost": str(breakdown.cost),
        "gross_profit": str(breakdown.gross_profit),
        "margin": str(breakdown.margin),
    }


async def propose_allowed_discount(
    *,
    customer_ref: str | None,
    product_id: str,
    quantity: int,
    requested_discount: str,
) -> dict[str, Any]:
    """Evaluate ``requested_discount`` against policy and return a JSON-safe decision."""

    with get_tracer().span("tool.propose_allowed_discount"):
        quote = await pricing.get_price(customer_ref, product_id, quantity)
        maximum_discount = (
            quote.maximum_discount
            if quote.maximum_discount is not None
            else get_settings().pricing_max_discount_pct
        )
        decision = pricing_policy.evaluate(
            customer_price=quote.customer_price,
            unit_cost=quote.unit_cost,
            requested_discount=Decimal(requested_discount),
            minimum_margin=quote.minimum_margin,
            maximum_discount=maximum_discount,
        )
    return {
        "allowed": decision.allowed,
        "max_allowed": str(decision.max_allowed),
        "resulting_margin": str(decision.resulting_margin),
        "requires_approval": decision.requires_approval,
        "reason": decision.reason.value,
    }
