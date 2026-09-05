import os

import uvicorn

from revenueflow.mcp.http_server import app


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
