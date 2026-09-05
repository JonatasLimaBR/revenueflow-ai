import asyncio

from revenueflow.services.analytics_sync import run


def main() -> int:
    result = asyncio.run(run())
    rows = " ".join(f"{name}={count}" for name, count in result.rows_loaded.items())
    print(f"analytics sync: {rows} errors={result.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
