"""Public read-only MCP server over Streamable HTTP (ADR-067).

Deployed as its own Cloud Run service (``infra/terraform/mcp_service.tf``),
reusing the same container image as the API (different ``command``). Exposes
only the 6 read tools from ``server.py`` — never the 5 action tools, which
stay on the personal stdio server (ADR-064). Public ingress (``allUsers``
invoker), gated by a single shared bearer token (``MCP_API_TOKEN``) — the
same trust model already used by ``/internal/approvals``/``/internal/handoffs``.
Requires the optional ``mcp`` extra; not exercised by the test suite (see
``mcp/auth.py`` for the testable half of this module).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from revenueflow.config import get_settings
from revenueflow.mcp.auth import bearer_gate
from revenueflow.mcp.server import lifespan, register_read_tools

mcp = FastMCP("revenueflow-readonly", lifespan=lifespan)
register_read_tools(mcp)

app = bearer_gate(mcp.streamable_http_app(), get_settings().mcp_api_token)
