import asyncio

from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.services.lead_lifecycle import SweepResult, sweep_stale


async def _run() -> SweepResult:
    await open_pool()
    try:
        return await sweep_stale()
    finally:
        await close_pool()


def main() -> int:
    result = asyncio.run(_run())
    print(f"lead sweep: swept={result.swept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
