import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
import pytest_asyncio
from psycopg import AsyncConnection

from revenueflow.config import get_settings
from revenueflow.repositories.db import close_pool, get_pool, open_pool

_ROOT = Path(__file__).resolve().parents[1]
_TRUNCATE = "TRUNCATE processed_event, dispatch, conversation_session, lead CASCADE"
_NO_DB_REASON = "no PostgreSQL reachable at DATABASE_URL (run `make db-up`)"


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_LIVE_EVAL"):
        return
    skip_live = pytest.mark.skip(reason="live eval: set RUN_LIVE_EVAL=1 and configure ADC")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def _database_reachable() -> bool:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2):
            return True
    except (psycopg.OperationalError, OSError):
        return False


_DB_REACHABLE = _database_reachable()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    if not _DB_REACHABLE:
        return
    for script in ("scripts/migrate.py", "scripts/seed.py"):
        subprocess.run([sys.executable, script], check=True, cwd=_ROOT)


@pytest_asyncio.fixture
async def conn(_schema: None) -> AsyncIterator[AsyncConnection[Any]]:
    if not _DB_REACHABLE:
        pytest.skip(_NO_DB_REASON)
    await open_pool()
    try:
        async with get_pool().connection() as connection:
            await connection.execute(_TRUNCATE)
            yield connection
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def db(_schema: None) -> AsyncIterator[None]:
    if not _DB_REACHABLE:
        pytest.skip(_NO_DB_REASON)
    await open_pool()
    try:
        async with get_pool().connection() as connection:
            await connection.execute(_TRUNCATE)
        yield
    finally:
        await close_pool()
