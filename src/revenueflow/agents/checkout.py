"""Deterministic Checkout Agent node (SPEC-013/014/015/016, ADR-051).

No open quote for the conversation -> build one from the resolved price and ask
for confirmation. An open ``SENT`` quote -> apply the SPEC-014 confirmation rule:
an unambiguous "close the deal" message creates the order (revalidating stock)
and the sandbox payment; anything else re-prompts. This node never calls the
model.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from revenueflow.agents.state import TurnState
from revenueflow.observability import get_tracer
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import checkout as checkout_svc
from revenueflow.tools import checkout as checkout_tools

_CENT = Decimal("0.01")


async def checkout_node(state: TurnState) -> dict[str, Any]:
    """Quote the deal, re-prompt for confirmation, or place the order."""

    with get_tracer().span("node.checkout"):
        async with unit_of_work() as conn:
            open_quote = await checkout_repo.get_open_quote(conn, state["conversation_id"])

        if open_quote is None:
            quote = await checkout_svc.quote_from_state(dict(state))
            result = await checkout_tools.create_quote(quote)
            item = quote.items[0]
            reply = (
                f"Proposta: {item['name']} x{item['quantity']} — R$ {quote.total} "
                f"(valida ate {result['expiration']}). Para fechar, responda 'sim, pode fechar'."
            )
            get_tracer().event("checkout.quote", attrs={"quote_id": result["quote_id"]})
            return {"reply": reply, "final_outcome": "quoted", "current_agent": "checkout"}

        if not checkout_svc.is_explicit_confirmation(state["customer_text"]):
            return {
                "reply": "Para fechar o pedido, responda 'sim, pode fechar'.",
                "final_outcome": "confirm_reprompt",
                "current_agent": "checkout",
            }

        outcome = await checkout_svc.confirm(open_quote)
        if outcome["outcome"] == "out_of_stock":
            available = outcome["available"]
            return {
                "reply": (
                    f"Nao consigo fechar: so ha {available} em estoque agora. "
                    "Refaca o pedido com a quantidade disponivel."
                ),
                "final_outcome": "out_of_stock",
                "current_agent": "checkout",
            }

        order_id = str(outcome["order_id"])
        get_tracer().event("checkout.ordered", attrs={"order_id": order_id})
        return {
            "reply": (
                f"Pedido #{order_id[:12]} confirmado; pagamento aprovado (sandbox). "
                f"Total R$ {open_quote.total.quantize(_CENT)}."
            ),
            "final_outcome": "ordered",
            "current_agent": "checkout",
        }
