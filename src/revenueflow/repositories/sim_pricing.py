from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchone

_PRODUCT_COST = "SELECT unit_cost, min_margin_pct FROM sim_product WHERE product_id = %s"

_CUSTOMER_PRICING = """
SELECT negotiated_price, max_discount_pct
FROM sim_customer_pricing
WHERE customer_id = %s AND product_id = %s
"""


async def product_cost(conn: AsyncConnection[Any], product_id: str) -> dict[str, Any]:
    row = await fetchone(conn, _PRODUCT_COST, (product_id,))
    if row is None:
        raise LookupError(product_id)
    return row


async def customer_pricing(
    conn: AsyncConnection[Any], customer_ref: str, product_id: str
) -> dict[str, Any] | None:
    return await fetchone(conn, _CUSTOMER_PRICING, (customer_ref, product_id))
