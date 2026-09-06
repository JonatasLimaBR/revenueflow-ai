import asyncio

from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.services.analytics_sync import SyncResult, run


async def _run() -> SyncResult:
    await open_pool()
    try:
        return await run()
    finally:
        await close_pool()


def main() -> int:
    result = asyncio.run(_run())
    rows = " ".join(f"{name}={count}" for name, count in result.rows_loaded.items())
    print(f"analytics sync: {rows} errors={result.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
