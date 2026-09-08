import psycopg
import pytest
import pytest_asyncio

from revenueflow.config import get_settings
from revenueflow.repositories.db import close_pool, get_pool, open_pool


@pytest_asyncio.fixture
async def pool_with_timeout(db: None, monkeypatch: pytest.MonkeyPatch) -> int:
    await close_pool()
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "200")
    get_settings.cache_clear()
    await open_pool()
    try:
        yield 200
    finally:
        await close_pool()
        get_settings.cache_clear()


async def test_statement_timeout_is_applied(pool_with_timeout: int) -> None:
    async with get_pool().connection() as conn:
        cur = await conn.execute("SHOW statement_timeout")
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == "200ms"


async def test_long_query_is_cancelled(pool_with_timeout: int) -> None:
    with pytest.raises(psycopg.errors.QueryCanceled):
        async with get_pool().connection() as conn:
            await conn.execute("SELECT pg_sleep(1)")


async def test_pool_is_sized_beyond_the_psycopg_default(db: None) -> None:
    """Regression: psycopg_pool defaults to a fixed pool of 4 connections
    (min_size=4, max_size=None -> 4) when unconfigured. That was too small
    for one turn's several sequential DB round-trips plus the LangGraph
    checkpointer's own pool plus routine /internal/* polling — found live
    as "error connecting in 'pool-1': connection timeout expired" during a
    real WhatsApp turn."""

    pool = get_pool()
    assert pool.min_size >= 2
    assert pool.max_size >= 10
