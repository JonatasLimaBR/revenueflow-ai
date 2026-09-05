import asyncio

from revenueflow.services.lead_lifecycle import sweep_stale


def main() -> int:
    result = asyncio.run(sweep_stale())
    print(f"lead sweep: swept={result.swept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
