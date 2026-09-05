"""Pure business logic behind the personal MCP server (ADR-064).

Read functions call the existing, already-tested ``repositories.analytics``
module (no new Postgres view, no ``Decimal``/dataclass serialization concerns
— those functions already return JSON-safe primitives, ADR-061/063). Action
functions call the existing, already-deployed internal HTTP routes
(``/internal/approvals``, ``/internal/handoffs``, ``/internal/audit``) through
an injected ``httpx.AsyncClient``, so nothing here duplicates the auth or
business logic that already lives in the API (ADR-050/054/055).

No dependency on the ``mcp`` package lives in this module — it is exercised by
the test suite without the optional ``mcp`` extra installed. ``server.py``
wires these functions to MCP tool decorators.
"""

from __future__ import annotations

from typing import Any

import httpx
from psycopg import AsyncConnection

from revenueflow.repositories import analytics as analytics_repo


async def revenue_summary(conn: AsyncConnection[Any]) -> dict[str, Any]:
    rows = await analytics_repo.conversation_revenue(conn)
    revenue = sum(r["revenue"] for r in rows)
    ai_cost = sum(r["ai_cost_usd"] for r in rows)
    orders = sum(r["orders"] for r in rows)
    return {
        "conversations": len(rows),
        "total_revenue": revenue,
        "total_margin": sum(r["margin_usd"] for r in rows),
        "total_recovered_revenue": sum(r["recovered_revenue_usd"] for r in rows),
        "total_ai_cost": ai_cost,
        "average_ticket": revenue / orders if orders else 0.0,
        "revenue_per_ai_cost_usd": revenue / ai_cost if ai_cost else 0.0,
    }


async def customer_360_list(conn: AsyncConnection[Any], limit: int) -> list[dict[str, Any]]:
    rows = await analytics_repo.customer_360_all(conn)
    return rows[:limit]


async def customer_360_one(conn: AsyncConnection[Any], customer_id: str) -> dict[str, Any]:
    rows = await analytics_repo.customer_360_all(conn)
    for row in rows:
        if row["customer_id"] == customer_id:
            return row
    return {"error": "not_found", "customer_id": customer_id}


async def lead_funnel(conn: AsyncConnection[Any]) -> dict[str, Any]:
    rows = await analytics_repo.lead_funnel(conn)
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {"by_status": by_status, "leads": rows}


async def opportunities_by_status(conn: AsyncConnection[Any], status: str) -> list[dict[str, Any]]:
    rows = await analytics_repo.opportunity_summary(conn)
    return [row for row in rows if row["status"] == status]


async def handoff_rate(conn: AsyncConnection[Any]) -> dict[str, Any]:
    row = (await analytics_repo.handoff_rate(conn))[0]
    total = row["total_turns"] or 0
    handoff = row["handoff_turns"] or 0
    return {**row, "handoff_rate": (handoff / total) if total else 0.0}


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def list_pending_approvals(client: httpx.AsyncClient, token: str) -> Any:
    resp = await client.get("/internal/approvals", headers=_auth_header(token))
    resp.raise_for_status()
    return resp.json()


async def decide_approval(
    client: httpx.AsyncClient,
    token: str,
    approval_id: str,
    decision: str,
    discount_pct: str | None,
) -> Any:
    body: dict[str, Any] = {"decision": decision}
    if discount_pct is not None:
        body["discount_pct"] = discount_pct
    resp = await client.post(
        f"/internal/approvals/{approval_id}", json=body, headers=_auth_header(token)
    )
    resp.raise_for_status()
    return resp.json()


async def list_pending_handoffs(client: httpx.AsyncClient, token: str) -> Any:
    resp = await client.get("/internal/handoffs", headers=_auth_header(token))
    resp.raise_for_status()
    return resp.json()


async def resolve_handoff(client: httpx.AsyncClient, token: str, handoff_id: str) -> Any:
    resp = await client.post(f"/internal/handoffs/{handoff_id}", headers=_auth_header(token))
    resp.raise_for_status()
    return resp.json()


async def audit_trail(client: httpx.AsyncClient, token: str, conversation_id: str) -> Any:
    resp = await client.get(f"/internal/audit/{conversation_id}", headers=_auth_header(token))
    resp.raise_for_status()
    return resp.json()
