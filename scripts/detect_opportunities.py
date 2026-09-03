import asyncio

from revenueflow.services.opportunity import scan


def main() -> int:
    result = asyncio.run(scan())
    print(
        f"opportunity scan: replenishment={result.replenishment} "
        f"quote_recovery={result.quote_recovery} created={result.created} "
        f"errors={result.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
