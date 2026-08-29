from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import execute

_CLAIM = "INSERT INTO processed_event (kind, key) VALUES (%s, %s) ON CONFLICT DO NOTHING"


async def claim(conn: AsyncConnection[Any], *, kind: str, key: str) -> bool:
    rowcount = await execute(conn, _CLAIM, (kind, key))
    return rowcount == 1
