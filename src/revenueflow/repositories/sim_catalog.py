from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchall, fetchone

_SEARCH = """
SELECT product_id, name, category, attrs, price_tiers
FROM sim_product
WHERE name ILIKE %s OR category ILIKE %s
ORDER BY name
LIMIT %s
"""

_GET = """
SELECT product_id, name, category, attrs, price_tiers
FROM sim_product
WHERE product_id = %s
"""


async def search(conn: AsyncConnection[Any], query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    return await fetchall(conn, _SEARCH, (pattern, pattern, limit))


async def get(conn: AsyncConnection[Any], product_id: str) -> dict[str, Any] | None:
    return await fetchone(conn, _GET, (product_id,))
