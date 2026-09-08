from typing import Any
from uuid import uuid4

import pytest

from revenueflow.agents import recommendation as recommendation_module
from revenueflow.agents.recommendation import recommendation_node

_360_KEYS = {
    "orders_12m",
    "revenue_12m",
    "average_ticket",
    "last_purchase",
    "purchase_interval_days",
    "preferred_products",
    "open_quotes",
}


def _state(customer_id: str | None) -> dict[str, Any]:
    return {
        "conversation_id": f"c-{uuid4().hex}",
        "customer_text": "quero uma bomba 1cv",
        "customer_id": customer_id,
    }


def _entry(result: dict[str, Any], tool: str) -> dict[str, Any] | None:
    return next((r for r in result["tool_results"] if r.get("tool") == tool), None)


async def test_node_attaches_360_for_known_customer(db: None) -> None:
    result = await recommendation_node(_state("CUST-001"))

    entry = _entry(result, "get_customer_360")
    assert entry is not None
    assert set(entry["result"]) == _360_KEYS


async def test_node_skips_360_for_unknown_caller(db: None) -> None:
    result = await recommendation_node(_state(None))

    assert _entry(result, "get_customer_360") is None


async def test_node_degrades_when_360_raises(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(_customer_id: str) -> dict[str, Any]:
        raise RuntimeError("customer_360 down")

    monkeypatch.setattr(recommendation_module, "get_customer_360", _boom)

    result = await recommendation_node(_state("CUST-001"))

    entry = _entry(result, "get_customer_360")
    assert entry == {"tool": "get_customer_360", "error": "unavailable"}


async def test_node_preserves_established_product_on_a_wordless_followup(db: None) -> None:
    """Regression: a pure negotiation follow-up ("pode fazer por 700?") never
    repeats the product name, so the naive keyword search finds nothing.
    Found live: recommendation_node always overwrote tool_results anyway,
    wiping the product a prior turn had already established and sending
    negotiation_node back to "Sobre qual produto...?" mid-negotiation."""

    state = _state("CUST-001")
    state["customer_text"] = "pode fazer por 700,00"
    state["tool_results"] = [
        {"tool": "search_products", "result": [{"product_id": "PMP-150-CEN"}]},
    ]

    result = await recommendation_node(state)

    assert result == {}


async def test_node_returns_empty_search_with_no_prior_product_to_preserve(db: None) -> None:
    state = _state("CUST-001")
    state["customer_text"] = "pode fazer por 700,00"

    result = await recommendation_node(state)

    assert _entry(result, "search_products") == {"tool": "search_products", "result": []}
