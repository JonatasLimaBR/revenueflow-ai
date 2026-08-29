"""Read-only Recommendation Agent step (SPEC-006/007, SPEC-029).

In this slice the node runs a deterministic, fixed tool sequence rather than a
real LLM tool-calling loop. The model-driven loop, where Gemini chooses which
registered tool to call and with what arguments, lands with the Vertex
integration. Every tool used here is read-only and comes from
``revenueflow.tools.registry``.

The naive substring search behind ``search_products`` returns nothing for a full
natural-language sentence, so the node first tries the raw customer text and
then falls back to individual terms until it obtains grounding rows. That term
derivation stands in for the query formulation the model will own later.
"""

from __future__ import annotations

import re
from typing import Any

from revenueflow.agents.state import TurnState
from revenueflow.observability import get_tracer
from revenueflow.tools.catalog import (
    get_customer_sales_context,
    get_inventory,
    search_products,
)

_TERM = re.compile(r"[0-9A-Za-zÀ-ÿ']{3,}")


def _search_candidates(text: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in (text.strip(), *_TERM.findall(text)):
        key = candidate.casefold()
        if candidate and key not in seen:
            seen.add(key)
            ordered.append(candidate)
    return ordered


async def _search(text: str) -> list[dict[str, Any]]:
    for candidate in _search_candidates(text):
        rows = await search_products(candidate, limit=3)
        if rows:
            return rows
    return []


async def recommendation_node(state: TurnState) -> dict[str, Any]:
    """Run the fixed read-only tool sequence and collect grounded results."""

    with get_tracer().span("node.recommendation"):
        products = await _search(state["customer_text"])
        tool_results: list[dict[str, Any]] = [{"tool": "search_products", "result": products}]
        if products:
            inventory = await get_inventory(str(products[0]["product_id"]), 1)
            tool_results.append({"tool": "get_inventory", "result": inventory})
        customer_id = state.get("customer_id")
        if customer_id:
            sales = await get_customer_sales_context(customer_id)
            tool_results.append({"tool": "get_customer_sales_context", "result": sales})
    return {"tool_results": tool_results}
