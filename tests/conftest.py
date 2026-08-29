import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from psycopg import AsyncConnection

from revenueflow.repositories.db import close_pool, get_pool, open_pool

_ROOT = Path(__file__).resolve().parents[1]
_TRUNCATE = "TRUNCATE processed_event, dispatch, conversation_session, lead CASCADE"


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    for script in ("scripts/migrate.py", "scripts/seed.py"):
        subprocess.run([sys.executable, script], check=True, cwd=_ROOT)


@pytest_asyncio.fixture
async def conn(_schema: None) -> AsyncIterator[AsyncConnection[Any]]:
    await open_pool()
    try:
        async with get_pool().connection() as connection:
            await connection.execute(_TRUNCATE)
            yield connection
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def db(_schema: None) -> AsyncIterator[None]:
    await open_pool()
    try:
        async with get_pool().connection() as connection:
            await connection.execute(_TRUNCATE)
        yield
    finally:
        await close_pool()
