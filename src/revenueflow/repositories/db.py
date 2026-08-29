from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from revenueflow.config import get_settings

_pool: AsyncConnectionPool[AsyncConnection[Any]] | None = None


def get_pool() -> AsyncConnectionPool[AsyncConnection[Any]]:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(get_settings().database_url, open=False)
    return _pool


async def open_pool() -> None:
    await get_pool().open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def unit_of_work() -> AsyncIterator[AsyncConnection[Any]]:
    async with get_pool().connection() as conn, conn.transaction():
        yield conn


@asynccontextmanager
async def read_connection() -> AsyncIterator[AsyncConnection[Any]]:
    async with get_pool().connection() as conn:
        yield conn


async def fetchone(
    conn: AsyncConnection[Any], sql: str, params: Sequence[Any] = ()
) -> dict[str, Any] | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(
    conn: AsyncConnection[Any], sql: str, params: Sequence[Any] = ()
) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def execute(conn: AsyncConnection[Any], sql: str, params: Sequence[Any] = ()) -> int:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount
