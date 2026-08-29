from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchone

_GET = "SELECT product_id, available, lead_time_days FROM sim_inventory WHERE product_id = %s"


async def get_available(
    conn: AsyncConnection[Any], product_id: str, quantity: int
) -> dict[str, Any]:
    row = await fetchone(conn, _GET, (product_id,))
    if row is None:
        return {
            "product_id": product_id,
            "available": 0,
            "fulfillable": False,
            "lead_time_days": None,
        }
    available = row["available"]
    return {
        "product_id": row["product_id"],
        "available": available,
        "fulfillable": available >= quantity,
        "lead_time_days": row["lead_time_days"],
    }
