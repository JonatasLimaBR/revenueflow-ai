import json
from typing import Any

import httpx
import pytest

from revenueflow.mcp import tools
from revenueflow.repositories import analytics as analytics_repo

_CONV_ROWS = [
    {
        "conversation_id": "c1",
        "ai_cost_usd": 1.0,
        "turns": 2,
        "last_at": "2026-09-05T00:00:00",
        "orders": 1,
        "revenue": 100.0,
        "margin_usd": 40.0,
        "recovered_revenue_usd": 0.0,
    },
    {
        "conversation_id": "c2",
        "ai_cost_usd": 1.0,
        "turns": 3,
        "last_at": "2026-09-05T00:00:00",
        "orders": 1,
        "revenue": 50.0,
        "margin_usd": 20.0,
        "recovered_revenue_usd": 50.0,
    },
]

_CUSTOMER_ROWS = [
    {"customer_id": "cust1", "orders_12m": 3, "revenue_12m": 300.0},
    {"customer_id": "cust2", "orders_12m": 0, "revenue_12m": 0.0},
]

_LEAD_ROWS = [
    {"lead_id": "l1", "status": "QUALIFIED", "created_at": "x"},
    {"lead_id": "l2", "status": "QUALIFIED", "created_at": "x"},
    {"lead_id": "l3", "status": "NEW", "created_at": "x"},
]

_OPPORTUNITY_ROWS = [
    {"opportunity_id": "o1", "status": "OPEN", "estimated_revenue": 10.0},
    {"opportunity_id": "o2", "status": "CONVERTED", "estimated_revenue": 20.0},
]


@pytest.fixture(autouse=True)
def _patch_analytics_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _conv(conn: object) -> list[dict[str, Any]]:
        return [dict(r) for r in _CONV_ROWS]

    async def _customer_360(conn: object) -> list[dict[str, Any]]:
        return [dict(r) for r in _CUSTOMER_ROWS]

    async def _lead_funnel(conn: object) -> list[dict[str, Any]]:
        return [dict(r) for r in _LEAD_ROWS]

    async def _opportunity_summary(conn: object) -> list[dict[str, Any]]:
        return [dict(r) for r in _OPPORTUNITY_ROWS]

    async def _handoff_rate(conn: object) -> list[dict[str, Any]]:
        return [{"total_turns": 10, "handoff_turns": 2}]

    monkeypatch.setattr(analytics_repo, "conversation_revenue", _conv)
    monkeypatch.setattr(analytics_repo, "customer_360_all", _customer_360)
    monkeypatch.setattr(analytics_repo, "lead_funnel", _lead_funnel)
    monkeypatch.setattr(analytics_repo, "opportunity_summary", _opportunity_summary)
    monkeypatch.setattr(analytics_repo, "handoff_rate", _handoff_rate)


async def test_revenue_summary_aggregates_rows() -> None:
    result = await tools.revenue_summary(conn=None)

    assert result["conversations"] == 2
    assert result["total_revenue"] == 150.0
    assert result["total_margin"] == 60.0
    assert result["total_recovered_revenue"] == 50.0
    assert result["total_ai_cost"] == 2.0
    assert result["average_ticket"] == 75.0
    assert result["revenue_per_ai_cost_usd"] == 75.0


async def test_revenue_summary_handles_zero_orders_and_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _empty(conn: object) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(analytics_repo, "conversation_revenue", _empty)

    result = await tools.revenue_summary(conn=None)

    assert result["average_ticket"] == 0.0
    assert result["revenue_per_ai_cost_usd"] == 0.0


async def test_customer_360_list_respects_limit() -> None:
    result = await tools.customer_360_list(conn=None, limit=1)

    assert len(result) == 1
    assert result[0]["customer_id"] == "cust1"


async def test_customer_360_one_found() -> None:
    result = await tools.customer_360_one(conn=None, customer_id="cust2")

    assert result["orders_12m"] == 0


async def test_customer_360_one_not_found() -> None:
    result = await tools.customer_360_one(conn=None, customer_id="missing")

    assert result == {"error": "not_found", "customer_id": "missing"}


async def test_lead_funnel_groups_by_status() -> None:
    result = await tools.lead_funnel(conn=None)

    assert result["by_status"] == {"QUALIFIED": 2, "NEW": 1}
    assert len(result["leads"]) == 3


async def test_opportunities_by_status_filters() -> None:
    result = await tools.opportunities_by_status(conn=None, status="OPEN")

    assert [o["opportunity_id"] for o in result] == ["o1"]


async def test_handoff_rate_computes_ratio() -> None:
    result = await tools.handoff_rate(conn=None)

    assert result["handoff_rate"] == 0.2


async def test_handoff_rate_zero_total(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _zero(conn: object) -> list[dict[str, Any]]:
        return [{"total_turns": 0, "handoff_turns": 0}]

    monkeypatch.setattr(analytics_repo, "handoff_rate", _zero)

    result = await tools.handoff_rate(conn=None)

    assert result["handoff_rate"] == 0.0


def _mock_client(handler: Any) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


async def test_list_pending_approvals_sends_bearer_token() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=[{"approval_id": "a1"}])

    async with _mock_client(handler) as client:
        result = await tools.list_pending_approvals(client, "tok123")

    assert seen["url"] == "http://test/internal/approvals"
    assert seen["auth"] == "Bearer tok123"
    assert result == [{"approval_id": "a1"}]


async def test_decide_approval_omits_discount_pct_when_not_override() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "approved"})

    async with _mock_client(handler) as client:
        await tools.decide_approval(client, "tok", "a1", "approve", None)

    assert seen["body"] == {"decision": "approve"}


async def test_decide_approval_includes_discount_pct_for_override() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "approved"})

    async with _mock_client(handler) as client:
        await tools.decide_approval(client, "tok", "a1", "approve_with_override", "0.20")

    assert seen["body"] == {"decision": "approve_with_override", "discount_pct": "0.20"}


async def test_list_pending_handoffs_calls_correct_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://test/internal/handoffs"
        return httpx.Response(200, json=[])

    async with _mock_client(handler) as client:
        result = await tools.list_pending_handoffs(client, "tok")

    assert result == []


async def test_resolve_handoff_calls_correct_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://test/internal/handoffs/h1"
        assert request.method == "POST"
        return httpx.Response(200, json={"status": "resolved"})

    async with _mock_client(handler) as client:
        result = await tools.resolve_handoff(client, "tok", "h1")

    assert result == {"status": "resolved"}


async def test_audit_trail_calls_correct_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://test/internal/audit/conv1"
        return httpx.Response(200, json=[{"turn_id": "t1"}])

    async with _mock_client(handler) as client:
        result = await tools.audit_trail(client, "tok", "conv1")

    assert result == [{"turn_id": "t1"}]


async def test_action_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    async with _mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await tools.list_pending_approvals(client, "bad-token")
