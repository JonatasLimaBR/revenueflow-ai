"""Checkout orchestration and the deterministic confirmation rule (SPEC-013/014/015/016).

``is_explicit_confirmation`` is the SPEC-014 gate: a pure phrase match, never an
LLM judgement. ``quote_from_state`` builds the versioned proposal from the price
already resolved by the pricing pipeline. ``confirm`` runs order + sandbox
payment in one transaction, idempotent on ``quote_id``.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from revenueflow.domain.models import Quote, QuoteStatus
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.tools import checkout as checkout_tools

_CENT = Decimal("0.01")
_ONE = Decimal("1")

_ACCEPT = (
    "sim pode fechar",
    "pode fechar",
    "pode faturar",
    "pode gerar o pedido",
    "confirmo o pedido",
    "confirmo",
    "fechado",
    "fechou negocio",
    "isso mesmo pode fechar",
)
_REJECT_HINT = ("acho que", "talvez", "quase", "?", "nao ", "nao,", "nao.")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_explicit_confirmation(text: str) -> bool:
    """Return ``True`` only for an unambiguous 'close the deal' message (SPEC-014)."""

    norm = _normalize(text).strip()
    if any(hint in norm for hint in _REJECT_HINT):
        return False
    return any(phrase in norm for phrase in _ACCEPT)


def _first_result(state: dict[str, Any], tool: str) -> dict[str, Any] | None:
    for entry in state.get("tool_results", []):
        if entry.get("tool") != tool:
            continue
        rows = entry.get("result") or []
        return dict(rows[0]) if rows else None
    return None


async def quote_from_state(state: dict[str, Any]) -> Quote:
    """Build a ``SENT`` quote from the resolved price and product in the turn state."""

    price = state["price_quote"]
    quantity = int(state.get("requested_quantity") or 1)
    discount = Decimal(str(state.get("checkout_discount") or "0"))
    product = _first_result(state, "search_products") or {}
    unit_price = Decimal(str(price["customer_price"])) * (_ONE - discount)
    total = (unit_price * quantity).quantize(_CENT)
    return Quote(
        quote_id=uuid4().hex,
        conversation_id=state["conversation_id"],
        customer_ref=state.get("customer_id"),
        items=[
            {
                "product_id": product.get("product_id"),
                "name": product.get("name"),
                "quantity": quantity,
                "unit_price": str(unit_price.quantize(_CENT)),
                "discount": str(discount),
            }
        ],
        total=total,
        expiration=datetime.fromisoformat(str(price["valid_until"])),
        status=QuoteStatus.SENT,
    )


async def confirm(quote: Quote) -> dict[str, Any]:
    """Create the order (revalidating stock) and run the sandbox payment."""

    order_res = await checkout_tools.create_order(quote)
    if order_res.get("error") == "out_of_stock":
        async with unit_of_work() as conn:
            await checkout_repo.set_quote_status(conn, quote.quote_id, QuoteStatus.EXPIRED)
        return {"outcome": "out_of_stock", "available": order_res["available"]}

    order_id = str(order_res["order_id"])
    await checkout_tools.create_payment_sandbox(order_id, quote.total)
    async with unit_of_work() as conn:
        await checkout_repo.mark_paid(conn, order_id, quote.quote_id)
    return {"outcome": "ordered", "order_id": order_id}
