"""Typed state threaded through the LangGraph turn graph."""

from __future__ import annotations

from typing import Any, TypedDict


class TurnInput(TypedDict):
    """The two fields a caller must provide to start a turn."""

    conversation_id: str
    customer_text: str


class TurnState(TurnInput, total=False):
    """Full turn state; every field below is produced by a graph node."""

    customer_id: str | None
    lead_id: str | None
    turn_id: str
    current_agent: str | None
    intent: str
    confidence: float
    tool_results: list[dict[str, Any]]
    requested_discount: str | None
    requested_quantity: int | None
    price_quote: dict[str, Any]
    policy_decision: dict[str, Any]
    pending_approval_id: str | None
    final_outcome: str
    reply: str
    handoff: bool
    handoff_reason: str
