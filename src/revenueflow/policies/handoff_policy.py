"""Deterministic human-handoff trigger rule (SPEC-026, ADR-013).

``should_handoff`` is a pure function: no I/O, no LLM. It decides whether a turn
must be transferred to a human and, if so, which controlled reason applies. The
precedence is fixed: an explicit request always wins, then a high-value order,
then low classification confidence.
"""

from __future__ import annotations

from decimal import Decimal

from revenueflow.domain.models import HandoffReason, Intent


def should_handoff(
    *,
    intent: str,
    confidence: float,
    resolved_total: Decimal | None,
    min_confidence: float,
    high_value_threshold: Decimal,
) -> HandoffReason | None:
    if intent == Intent.HUMAN_SUPPORT.value:
        return HandoffReason.EXPLICIT_REQUEST
    if resolved_total is not None and resolved_total > high_value_threshold:
        return HandoffReason.HIGH_VALUE_ORDER
    if confidence < min_confidence:
        return HandoffReason.LOW_CONFIDENCE
    return None
