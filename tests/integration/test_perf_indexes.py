from typing import Any

from psycopg import AsyncConnection

_EXPECTED = {
    "opportunity_status_created_idx",
    "handoff_status_created_idx",
    "approval_status_created_idx",
    "quote_customer_ref_open_idx",
}


async def test_migration_0011_creates_indexes(conn: AsyncConnection[Any]) -> None:
    cur = await conn.execute(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename IN ('opportunity', 'handoff', 'approval', 'quote')"
    )
    names = {row[0] for row in await cur.fetchall()}
    assert _EXPECTED <= names


async def test_tables_still_queryable(conn: AsyncConnection[Any]) -> None:
    for table in ("opportunity", "handoff", "approval", "quote"):
        cur = await conn.execute(f"SELECT count(*) FROM {table}")
        assert await cur.fetchone() is not None
