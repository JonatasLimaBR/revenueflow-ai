import asyncio

from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.services.expiration import SweepResult, sweep


async def _run() -> SweepResult:
    await open_pool()
    try:
        return await sweep()
    finally:
        await close_pool()


def main() -> int:
    result = asyncio.run(_run())
    print(
        f"expiration sweep: approvals_expired={result.approvals_expired} "
        f"quotes_expired={result.quotes_expired} handoffs_expired={result.handoffs_expired}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
