import asyncio

from revenueflow.services.analytics_sync import run


def main() -> int:
    result = asyncio.run(run())
    print(
        f"analytics sync: conversation_rows={result.conversation_rows} "
        f"outcome_rows={result.outcome_rows} errors={result.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
