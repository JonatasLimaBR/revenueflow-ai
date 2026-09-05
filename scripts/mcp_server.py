from revenueflow.mcp.server import mcp


def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
