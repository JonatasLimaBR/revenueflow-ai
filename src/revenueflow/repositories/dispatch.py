from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import execute

_RESERVE = "INSERT INTO dispatch (dispatch_key) VALUES (%s) ON CONFLICT DO NOTHING"


async def reserve(conn: AsyncConnection[Any], *, dispatch_key: str) -> bool:
    rowcount = await execute(conn, _RESERVE, (dispatch_key,))
    return rowcount == 1
