import asyncio

from revenueflow.services.campaign import run


def main() -> int:
    result = asyncio.run(run())
    print(
        f"campaign run: sent={result.sent} skipped={result.skipped} "
        f"failed={result.failed} errors={result.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
