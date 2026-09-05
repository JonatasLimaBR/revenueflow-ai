"""Deterministic lead-status transitions (PRD-015 Lead 360, ADR-062).

``advance`` is pure: no I/O, no LLM. It never downgrades a lead (monotonic)
and never moves a terminal lead (``WON``/``LOST``) anywhere else.
"""

from __future__ import annotations

from revenueflow.domain.models import Intent, LeadStatus

_RANK = {
    LeadStatus.NEW: 0,
    LeadStatus.QUALIFYING: 1,
    LeadStatus.QUALIFIED: 2,
    LeadStatus.PROPOSAL: 3,
    LeadStatus.WON: 4,
    LeadStatus.LOST: 4,
}

_QUALIFYING_INTENTS = frozenset(
    {Intent.PRODUCT_SEARCH, Intent.RECOMMENDATION, Intent.STOCK_REQUEST, Intent.PRICE_REQUEST}
)
_QUALIFIED_INTENTS = frozenset({Intent.NEGOTIATION, Intent.QUOTE_REQUEST})


def advance(current: LeadStatus, *, intent: Intent | None, final_outcome: str | None) -> LeadStatus:
    """Return the next status for ``current`` given this turn's signals."""

    if current in (LeadStatus.WON, LeadStatus.LOST):
        return current

    if final_outcome == "ordered":
        target = LeadStatus.WON
    elif final_outcome == "quoted":
        target = LeadStatus.PROPOSAL
    elif intent in _QUALIFIED_INTENTS:
        target = LeadStatus.QUALIFIED
    elif intent in _QUALIFYING_INTENTS:
        target = LeadStatus.QUALIFYING
    else:
        return current

    return target if _RANK[target] > _RANK[current] else current
