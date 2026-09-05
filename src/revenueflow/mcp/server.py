"""FastMCP wiring for the personal RevenueFlow MCP server (ADR-064).

Entry point: ``scripts/mcp_server.py`` (stdio transport, for Claude Desktop /
Claude Code — the confirmed personal-use consumer). Business logic lives in
``revenueflow.mcp.tools``; this module only wires each function to a
``@mcp.tool()`` decorator and manages the DB pool lifespan. Requires the
optional ``mcp`` extra (``pip install -e ".[mcp]"``) — nothing else in the app
imports this module, so it is not exercised by the test suite or by CI.

``_register_read_tools``/``_register_action_tools`` are split out (not just
inlined below ``mcp = FastMCP(...)``) so ``http_server.py`` (the read-only
remote variant, ADR-067) can reuse the exact same 6 read tools without
duplicating their wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP
from revenueflow.config import get_settings
from revenueflow.mcp import tools
from revenueflow.repositories.db import close_pool, open_pool, unit_of_work


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncIterator[None]:
    await open_pool()
    try:
        yield
    finally:
        await close_pool()


def _api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=get_settings().revenueflow_api_base_url, timeout=10.0)


def register_read_tools(mcp: FastMCP) -> None:
    """The 6 read-only tools — safe to expose on the public read-only HTTP server."""

    @mcp.tool()
    async def get_revenue_summary() -> dict[str, Any]:
        """Receita, margem, receita recuperada e custo de IA agregados (todas as conversas)."""
        async with unit_of_work() as conn:
            return await tools.revenue_summary(conn)

    @mcp.tool()
    async def list_customer_360(limit: int = 50) -> list[dict[str, Any]]:
        """Customer 360 (pedidos/receita/última compra/produto preferido) por cliente."""
        async with unit_of_work() as conn:
            return await tools.customer_360_list(conn, limit)

    @mcp.tool()
    async def get_customer_360(customer_id: str) -> dict[str, Any]:
        """Customer 360 de um único cliente."""
        async with unit_of_work() as conn:
            return await tools.customer_360_one(conn, customer_id)

    @mcp.tool()
    async def list_lead_funnel() -> dict[str, Any]:
        """Funil de leads: contagem por status + a lista completa."""
        async with unit_of_work() as conn:
            return await tools.lead_funnel(conn)

    @mcp.tool()
    async def list_opportunities(status: str = "OPEN") -> list[dict[str, Any]]:
        """Oportunidades (recompra atrasada / quote parada) pelo status informado."""
        async with unit_of_work() as conn:
            return await tools.opportunities_by_status(conn, status)

    @mcp.tool()
    async def get_handoff_rate() -> dict[str, Any]:
        """Taxa de handoff para humano: turnos com handoff / total de turnos."""
        async with unit_of_work() as conn:
            return await tools.handoff_rate(conn)


def register_action_tools(mcp: FastMCP) -> None:
    """The 5 action tools — personal stdio server only, never the public HTTP one."""

    @mcp.tool()
    async def list_pending_approvals() -> Any:
        """Aprovações de desconto pendentes."""
        settings = get_settings()
        async with _api_client() as client:
            return await tools.list_pending_approvals(client, settings.approval_api_token)

    @mcp.tool()
    async def decide_approval(
        approval_id: str, decision: str, discount_pct: str | None = None
    ) -> Any:
        """Decide uma aprovação pendente: approve / approve_with_override / reject."""
        settings = get_settings()
        async with _api_client() as client:
            return await tools.decide_approval(
                client, settings.approval_api_token, approval_id, decision, discount_pct
            )

    @mcp.tool()
    async def list_pending_handoffs() -> Any:
        """Handoffs para humano pendentes."""
        settings = get_settings()
        async with _api_client() as client:
            return await tools.list_pending_handoffs(client, settings.handoff_api_token)

    @mcp.tool()
    async def resolve_handoff(handoff_id: str) -> Any:
        """Marca um handoff como resolvido."""
        settings = get_settings()
        async with _api_client() as client:
            return await tools.resolve_handoff(client, settings.handoff_api_token, handoff_id)

    @mcp.tool()
    async def get_audit_trail(conversation_id: str) -> Any:
        """Reconstrói o histórico auditado de uma conversa (turnos + eventos)."""
        settings = get_settings()
        async with _api_client() as client:
            return await tools.audit_trail(client, settings.handoff_api_token, conversation_id)


mcp = FastMCP("revenueflow", lifespan=lifespan)
register_read_tools(mcp)
register_action_tools(mcp)
