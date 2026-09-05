"""Bearer-token ASGI gate for the public read-only MCP HTTP server (ADR-067).

Plain ASGI — no dependency on the ``mcp`` package, so it's testable in the
standard suite without the optional extra installed. Mirrors the same
trust model already used by ``/internal/approvals``/``/internal/handoffs``:
the service is public (``allUsers`` invoker on Cloud Run); this bearer check
is the only gate. ``lifespan`` scope events are always passed through
unconditionally — gating them would break the wrapped app's startup/shutdown
(the MCP session manager starts on the ASGI ``lifespan.startup`` event).
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Any

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def bearer_gate(app: ASGIApp, token: str) -> ASGIApp:
    async def _gated(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or _authorized(scope, token):
            await app(scope, receive, send)
            return
        await _unauthorized(send)

    return _gated


def _authorized(scope: Scope, token: str) -> bool:
    if token == "":
        return False
    headers = dict(scope.get("headers") or [])
    auth = headers.get(b"authorization", b"").decode("latin-1")
    return secrets.compare_digest(auth, f"Bearer {token}")


async def _unauthorized(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": b'{"detail":"unauthorized"}'})
