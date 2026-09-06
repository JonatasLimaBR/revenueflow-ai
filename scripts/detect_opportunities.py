import asyncio

from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.services.opportunity import ScanResult, scan


async def _run() -> ScanResult:
    await open_pool()
    try:
        return await scan()
    finally:
        await close_pool()


def main() -> int:
    result = asyncio.run(_run())
    print(
        f"opportunity scan: replenishment={result.replenishment} "
        f"quote_recovery={result.quote_recovery} created={result.created} "
        f"errors={result.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
