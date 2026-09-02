"""Deterministic write tools for the Checkout Agent (SPEC-013/015/016, ADR-025/029).

These are the only place ``quote`` / ``sales_order`` / ``payment`` rows are
written. They never call the model. ``create_order`` revalidates stock through
the same read-only inventory tool before inserting; the payment tool is a
sandbox stub that always approves and stores nothing sensitive (SPEC-016).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from revenueflow.domain.models import (
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Quote,
)
from revenueflow.observability import get_tracer
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.tools.catalog import get_inventory


async def create_quote(quote: Quote) -> dict[str, Any]:
    """Persist a ``SENT`` quote; return the open quote (new or pre-existing)."""

    with get_tracer().span("tool.create_quote", attrs={"conversation_id": quote.conversation_id}):
        async with unit_of_work() as conn:
            stored = await checkout_repo.create_quote(conn, quote)
    return {
        "quote_id": stored.quote_id,
        "total": str(stored.total),
        "expiration": stored.expiration.isoformat(),
        "status": stored.status.value,
    }


async def create_order(quote: Quote) -> dict[str, Any]:
    """Revalidate stock, then insert the order idempotently on ``quote_id``."""

    item = quote.items[0]
    product_id = str(item["product_id"])
    quantity = int(item["quantity"])
    with get_tracer().span("tool.create_order", attrs={"quote_id": quote.quote_id}):
        inventory = await get_inventory(product_id, quantity)
        if not inventory["fulfillable"]:
            return {"error": "out_of_stock", "available": inventory["available"]}
        order = Order(
            order_id=uuid4().hex,
            quote_id=quote.quote_id,
            customer_ref=quote.customer_ref,
            items=quote.items,
            total=quote.total,
            status=OrderStatus.CONFIRMED,
        )
        async with unit_of_work() as conn:
            stored = await checkout_repo.create_order(conn, order)
    return {"order_id": stored.order_id, "status": stored.status.value}


async def create_payment_sandbox(order_id: str, amount: Decimal) -> dict[str, Any]:
    """Sandbox payment: always approves; persists only ``order_id`` and ``amount``."""

    with get_tracer().span("tool.create_payment_sandbox", attrs={"order_id": order_id}):
        payment = Payment(
            payment_id=uuid4().hex,
            order_id=order_id,
            amount=amount,
            status=PaymentStatus.APPROVED,
        )
        async with unit_of_work() as conn:
            await checkout_repo.create_payment(conn, payment)
    return {"payment_id": payment.payment_id, "status": "APPROVED", "amount": str(amount)}
