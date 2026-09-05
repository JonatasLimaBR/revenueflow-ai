from typing import Any

from revenueflow.mcp.auth import bearer_gate

_TOKEN = "s3cr3t-token"


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


class _FakeApp:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        self.called = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _http_scope(auth_header: bytes | None) -> dict[str, Any]:
    headers = [(b"authorization", auth_header)] if auth_header is not None else []
    return {"type": "http", "headers": headers}


async def test_correct_bearer_passes_through() -> None:
    inner = _FakeApp()
    gated = bearer_gate(inner, _TOKEN)
    send = _Recorder()

    await gated(_http_scope(f"Bearer {_TOKEN}".encode()), _receive, send)

    assert inner.called is True
    assert send.messages[0]["status"] == 200


async def test_wrong_bearer_returns_401() -> None:
    inner = _FakeApp()
    gated = bearer_gate(inner, _TOKEN)
    send = _Recorder()

    await gated(_http_scope(b"Bearer wrong-token"), _receive, send)

    assert inner.called is False
    assert send.messages[0]["status"] == 401


async def test_missing_header_returns_401() -> None:
    inner = _FakeApp()
    gated = bearer_gate(inner, _TOKEN)
    send = _Recorder()

    await gated(_http_scope(None), _receive, send)

    assert inner.called is False
    assert send.messages[0]["status"] == 401


async def test_empty_configured_token_rejects_everything() -> None:
    inner = _FakeApp()
    gated = bearer_gate(inner, "")
    send = _Recorder()

    await gated(_http_scope(b"Bearer "), _receive, send)

    assert inner.called is False
    assert send.messages[0]["status"] == 401


async def test_lifespan_scope_always_passed_through() -> None:
    inner = _FakeApp()
    gated = bearer_gate(inner, _TOKEN)
    send = _Recorder()

    await gated({"type": "lifespan"}, _receive, send)

    assert inner.called is True
