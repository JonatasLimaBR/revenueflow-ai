import asyncio

from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.services.campaign import CampaignResult, run


async def _run() -> CampaignResult:
    await open_pool()
    try:
        return await run()
    finally:
        await close_pool()


def main() -> int:
    result = asyncio.run(_run())
    print(
        f"campaign run: sent={result.sent} skipped={result.skipped} "
        f"failed={result.failed} errors={result.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
