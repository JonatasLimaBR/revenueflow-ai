from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchall

_CONTEXT_FOR = """
SELECT product_id, last_qty, last_order_at
FROM sim_customer_sales
WHERE customer_id = %s
ORDER BY last_order_at DESC
LIMIT %s
"""


async def context_for(
    conn: AsyncConnection[Any], customer_id: str, *, limit: int = 10
) -> list[dict[str, Any]]:
    return await fetchall(conn, _CONTEXT_FOR, (customer_id, limit))
