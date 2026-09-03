"""Human-handoff orchestration (SPEC-026/027).

``build_context`` assembles the structured summary a human agent needs to pick
up a conversation without reading it in full — deterministically, from turn
state plus the customer row and the customer's open opportunity. No LLM.
``create`` / ``list_pending`` / ``resolve`` wrap the repository.
"""

from __future__ import annotations

from typing import Any

from revenueflow.domain.models import HandoffReason, HandoffStatus, OpportunityStatus
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import read_connection, unit_of_work


async def build_context(state: dict[str, Any]) -> dict[str, Any]:
    tool_results = state.get("tool_results", [])
    products = [
        {"product_id": product.get("product_id"), "name": product.get("name")}
        for entry in tool_results
        if entry.get("tool") == "search_products"
        for product in (entry.get("result") or [])
    ]
    price_quote = state.get("price_quote")
    quote = (
        {
            "customer_price": price_quote["customer_price"],
            "valid_until": price_quote["valid_until"],
        }
        if price_quote
        else None
    )
    requested_discount = state.get("requested_discount")
    objections = [f"desconto solicitado {requested_discount}"] if requested_discount else []

    customer_id = state.get("customer_id")
    customer: dict[str, Any] | None = None
    next_best_action: str | None = None
    if customer_id:
        async with read_connection() as conn:
            row = await customer_repo.get_by_id(conn, customer_id)
            opportunities = await opportunity_repo.list_by_status(conn, OpportunityStatus.OPEN)
        if row is not None:
            customer = {
                "customer_id": row.customer_id,
                "name": row.name,
                "segment": row.segment,
            }
        mine = [o for o in opportunities if o.customer_id == customer_id]
        if mine:
            next_best_action = max(mine, key=lambda o: o.created_at).recommended_action

    intent = str(state.get("intent", "unknown"))
    summary = (
        f"Cliente com intent '{intent}'. {len(products)} produto(s) recuperado(s). "
        f"{'Cotacao em aberto.' if quote else 'Sem cotacao.'} "
        f"{'Pediu desconto.' if objections else ''}"
    ).strip()
    return {
        "conversation_summary": summary,
        "customer": customer,
        "intent": intent,
        "products": products,
        "quote": quote,
        "objections": objections,
        "reason": str(state.get("handoff_reason", "unknown")),
        "next_best_action": next_best_action,
    }


async def create(conversation_id: str, reason: HandoffReason, context: dict[str, Any]) -> None:
    async with unit_of_work() as conn:
        await handoff_repo.create(conn, conversation_id, reason, context)


async def list_pending() -> list[dict[str, Any]]:
    async with read_connection() as conn:
        rows = await handoff_repo.list_by_status(conn, HandoffStatus.PENDING)
    return [
        {
            "handoff_id": row.handoff_id,
            "conversation_id": row.conversation_id,
            "reason": row.reason.value,
            "context": row.context,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


async def resolve(handoff_id: str) -> bool:
    async with unit_of_work() as conn:
        return await handoff_repo.resolve(conn, handoff_id) == 1
