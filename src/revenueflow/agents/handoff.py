"""Human-handoff graph node and the shared handoff-dict builder.

This module lives apart from ``graph.py`` so ``negotiation.py`` can build a
handoff dict (``to_handoff``) without importing ``graph.py`` (which imports the
node modules — the cycle ``graph -> negotiation -> graph`` is what this avoids).
It only depends on ``services`` / ``repositories`` / ``domain``.

``handoff_node`` is terminal: it builds the structured context (SPEC-027),
persists one PENDING ``Handoff`` (idempotent), marks the session
``HUMAN_HANDOFF``, and returns the fixed transfer reply. A ``build_context``
failure degrades to a minimal context but never blocks the transfer.
"""

from __future__ import annotations

import logging
from typing import Any

from revenueflow.agents.state import TurnState
from revenueflow.domain.models import HandoffReason, SessionStatus
from revenueflow.observability import get_tracer
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import handoff as handoff_svc

_LOGGER = logging.getLogger(__name__)

_HANDOFF_REPLY = (
    "Vou transferir voce para um atendente humano; ele vai dar sequencia ao seu atendimento."
)


def to_handoff(reason: str) -> dict[str, Any]:
    """Return the state patch that routes a turn to the handoff node."""

    return {
        "handoff": True,
        "handoff_reason": reason,
        "reply": _HANDOFF_REPLY,
        "final_outcome": "handoff",
    }


async def handoff_node(state: TurnState) -> dict[str, Any]:
    """Persist the handoff with structured context and mark the session."""

    reason = HandoffReason(state.get("handoff_reason", HandoffReason.RESPOND.value))
    conversation_id = state["conversation_id"]
    try:
        context = await handoff_svc.build_context(dict(state))
    except Exception:
        get_tracer().event("handoff.context_failed", attrs={"conversation_id": conversation_id})
        _LOGGER.exception("build_context failed for %s", conversation_id)
        context = {"reason": reason.value, "intent": str(state.get("intent", "unknown"))}
    async with unit_of_work() as conn:
        await handoff_repo.create(conn, conversation_id, reason, context)
        await session_repo.update_status(conn, conversation_id, SessionStatus.HUMAN_HANDOFF)
    get_tracer().end(outcome="handoff", handoff=True)
    return {"reply": _HANDOFF_REPLY, "final_outcome": "handoff", "handoff": True}
