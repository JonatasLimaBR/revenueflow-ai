"""Read-only catalog, inventory, and sales-context tools.

These four callables are the only tools the Recommendation Agent may invoke
(D5, SPEC-024/025). Each opens its own read-only connection, delegates to a
simulator repository, validates the result through a Pydantic schema, and
returns JSON-serializable data. None of them write.
"""

from __future__ import annotations

from typing import Any

from revenueflow.observability import get_tracer
from revenueflow.repositories import sim_catalog, sim_inventory, sim_sales
from revenueflow.repositories.db import read_connection
from revenueflow.tools.schemas import InventoryView, ProductSummary, SalesRow


async def search_products(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return catalog rows matching ``query`` as JSON-serializable dicts."""

    with get_tracer().span("tool.search_products", attrs={"query": query, "limit": limit}):
        async with read_connection() as conn:
            rows = await sim_catalog.search(conn, query, limit=limit)
        return [ProductSummary(**row).model_dump(mode="json") for row in rows]


async def get_product_details(product_id: str) -> dict[str, Any] | None:
    """Return a single catalog row, or ``None`` when the id is unknown."""

    with get_tracer().span("tool.get_product_details", attrs={"product_id": product_id}):
        async with read_connection() as conn:
            row = await sim_catalog.get(conn, product_id)
        if row is None:
            return None
        return ProductSummary(**row).model_dump(mode="json")


async def get_inventory(product_id: str, quantity: int = 1) -> dict[str, Any]:
    """Return an availability snapshot for ``product_id`` and ``quantity``."""

    with get_tracer().span(
        "tool.get_inventory", attrs={"product_id": product_id, "quantity": quantity}
    ):
        async with read_connection() as conn:
            row = await sim_inventory.get_available(conn, product_id, quantity)
        return InventoryView(**row).model_dump(mode="json")


async def get_customer_sales_context(customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent orders for a known customer as JSON-serializable dicts."""

    with get_tracer().span(
        "tool.get_customer_sales_context",
        attrs={"customer_id": customer_id, "limit": limit},
    ):
        async with read_connection() as conn:
            rows = await sim_sales.context_for(conn, customer_id, limit=limit)
        return [SalesRow(**row).model_dump(mode="json") for row in rows]
