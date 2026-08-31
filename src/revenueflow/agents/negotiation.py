"""Negotiation Agent step and the persistent policy gate (DESIGN §4.5).

``negotiation_node`` runs after the read-only Recommendation step for
discount-shaped intents. It reads price and margin through the deterministic
pricing tools, then either quotes a price, proposes a discount that is within
policy, or -- when the ask breaks policy -- records an ``Approval(PENDING)`` and
hands off. ``await_approval_node`` fires the persistent ``interrupt()`` so the
graph stops until a human decides (SPEC-011/012, ADR-039/037/012).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from langgraph.types import interrupt

from revenueflow.agents.state import TurnState
from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.observability import get_tracer
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import extract_discount
from revenueflow.tools import pricing as tools_pricing

_ONE = Decimal("1")
_CENT = Decimal("0.01")

_CLARIFY_REPLY = "Sobre qual produto você gostaria de negociar?"
_PENDING_REPLY = "Sua solicitação foi encaminhada para aprovação; retornamos em breve."


def _product_id(state: TurnState) -> str | None:
    """Return the first ``search_products`` hit recorded by the Recommendation step."""

    for entry in state.get("tool_results", []):
        if entry.get("tool") != "search_products":
            continue
        hits = entry.get("result") or []
        if hits:
            return str(hits[0]["product_id"])
        return None
    return None


async def negotiation_node(state: TurnState) -> dict[str, Any]:
    """Quote, propose within policy, or open a human approval and hand off."""

    with get_tracer().span("node.negotiation"):
        product_id = _product_id(state)
        if product_id is None:
            return {"reply": _CLARIFY_REPLY, "final_outcome": "clarify"}

        requested, quantity = extract_discount(state["customer_text"])
        qty = quantity or 1
        customer_ref = state.get("customer_id")
        quote = await tools_pricing.get_price(customer_ref, product_id, qty)
        valid_until = quote["valid_until"]

        if requested is None:
            price = Decimal(quote["customer_price"]).quantize(_CENT)
            reply = f"O preço para {qty} un é R$ {price} (válido até {valid_until})."
            return {"reply": reply, "final_outcome": "quoted", "price_quote": quote}

        margin = await tools_pricing.calculate_margin(
            quote["customer_price"], quote["unit_cost"], str(requested)
        )
        decision = await tools_pricing.propose_allowed_discount(
            customer_ref=customer_ref,
            product_id=product_id,
            quantity=qty,
            requested_discount=str(requested),
        )
        get_tracer().event("negotiation.policy", attrs={"reason": decision["reason"]})

        if not decision["requires_approval"]:
            applied = min(requested, Decimal(decision["max_allowed"]))
            final = (Decimal(quote["customer_price"]) * (_ONE - applied)).quantize(_CENT)
            pct = f"{applied:.0%}"
            reply = f"Consigo {pct} para {qty} un: R$ {final} (válido até {valid_until})."
            return {
                "reply": reply,
                "final_outcome": "proposed",
                "price_quote": quote,
                "policy_decision": decision,
            }

        approval = Approval(
            approval_id=uuid4().hex,
            conversation_id=state["conversation_id"],
            turn_id=state["turn_id"],
            reason=decision["reason"],
            requested_discount=requested,
            current_margin=Decimal(margin["margin"]),
            resulting_margin=Decimal(decision["resulting_margin"]),
            amount=(Decimal(quote["customer_price"]) * qty).quantize(_CENT),
            customer_ref=customer_ref,
            status=ApprovalStatus.PENDING,
        )
        async with unit_of_work() as conn:
            await approval_repo.create_pending(conn, approval)

    return {
        "reply": _PENDING_REPLY,
        "pending_approval_id": approval.approval_id,
        "policy_decision": decision,
        "final_outcome": "pending_approval",
    }


async def await_approval_node(state: TurnState) -> dict[str, Any]:
    """Fire the persistent interrupt so the graph pauses for a human decision."""

    with get_tracer().span("node.await_approval"):
        interrupt({"approval_id": state["pending_approval_id"]})
    return {}
