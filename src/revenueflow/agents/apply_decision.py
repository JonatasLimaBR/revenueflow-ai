"""Resume node: apply a human's approval decision (ADR-050).

Runs after ``await_approval_node`` returns the decision payload. It is fully
deterministic -- price and margin come from the quote frozen in the checkpoint
state, never from the model -- and produces the final customer reply for one of
four outcomes: approved, overridden, rejected, expired.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from revenueflow.agents.state import TurnState
from revenueflow.observability import get_tracer
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work

_ONE = Decimal("1")
_CENT = Decimal("0.01")


async def apply_decision_node(state: TurnState) -> dict[str, Any]:
    """Turn the approval decision into a grounded final reply."""

    with get_tracer().span("node.apply_decision"):
        payload = state["approval_decision"]
        async with unit_of_work() as conn:
            approval = await approval_repo.get(conn, str(state["pending_approval_id"]))

        quote = state["price_quote"]
        qty = state.get("requested_quantity") or 1
        requested = Decimal(str(state["requested_discount"]))
        customer_price = Decimal(quote["customer_price"])
        valid_until = quote["valid_until"]

        expired = (
            approval is not None
            and approval.expires_at is not None
            and datetime.now(UTC) > approval.expires_at
        )
        decision = "expired" if expired else str(payload["decision"])

        if decision in ("expired", "reject"):
            outcome = "expired" if decision == "expired" else "rejected"
            base = customer_price.quantize(_CENT)
            reason = " a tempo" if decision == "expired" else ""
            reply = (
                f"Nao consegui aprovar o desconto solicitado{reason}. O melhor valor "
                f"dentro da politica para {qty} un fica em R$ {base} (valido ate {valid_until})."
            )
            return {"reply": reply, "final_outcome": outcome, "current_agent": "negotiation"}

        if decision == "approve":
            applied = requested
            outcome = "approved"
        else:
            override = max(Decimal("0"), Decimal(str(payload["discount_pct"])))
            applied = min(requested, override)
            outcome = "overridden"

        final = (customer_price * (_ONE - applied)).quantize(_CENT)
        reply = (
            f"Aprovado: {applied:.0%} de desconto para {qty} un — "
            f"R$ {final} (valido ate {valid_until})."
        )
        return {
            "reply": reply,
            "final_outcome": outcome,
            "checkout_discount": str(applied),
            "current_agent": "negotiation",
        }
