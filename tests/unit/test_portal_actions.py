"""Confirms the portal's action routes go through mcp.tools (which calls the
internal HTTP routes via httpx) and never write to approval/handoff tables
directly (ADR-037/ADR-073)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from revenueflow.config import get_settings
from revenueflow.portal import views


def _mock_client(handler: Any) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


@pytest.fixture(autouse=True)
def _patch_internal_client(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["auth"] = request.headers.get("authorization")
        if request.content:
            seen["body"] = json.loads(request.content)
        if "/internal/approvals" in str(request.url) and request.method == "GET":
            return httpx.Response(200, json=[{"approval_id": "a1"}])
        if "/internal/handoffs" in str(request.url) and request.method == "GET":
            return httpx.Response(200, json=[{"handoff_id": "h1"}])
        return httpx.Response(200, json={"status": "ok"})

    monkeypatch.setattr(views, "_internal_client", lambda: _mock_client(handler))
    get_settings.cache_clear()
    return seen


async def test_list_approvals_calls_internal_route(
    _patch_internal_client: dict[str, Any],
) -> None:
    client = views._internal_client()
    async with client:
        from revenueflow.mcp import tools as mcp_tools

        result = await mcp_tools.list_pending_approvals(client, "tok")
    assert result == [{"approval_id": "a1"}]
    assert _patch_internal_client["url"] == "http://test/internal/approvals"


async def test_decide_approval_route_never_writes_db_directly(
    _patch_internal_client: dict[str, Any],
) -> None:
    response = await views.decide_approval(
        session=None,  # type: ignore[arg-type]
        approval_id="a1",
        decision="approve",
        discount_pct=None,
    )
    assert response.status_code == 303
    assert _patch_internal_client["url"] == "http://test/internal/approvals/a1"
    assert _patch_internal_client["method"] == "POST"
    assert _patch_internal_client["body"] == {"decision": "approve"}


async def test_resolve_handoff_route_calls_internal_route(
    _patch_internal_client: dict[str, Any],
) -> None:
    response = await views.resolve_handoff(session=None, handoff_id="h1")  # type: ignore[arg-type]
    assert response.status_code == 303
    assert _patch_internal_client["url"] == "http://test/internal/handoffs/h1"
    assert _patch_internal_client["method"] == "POST"
