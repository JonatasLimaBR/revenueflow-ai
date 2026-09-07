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
from mcp.server.transport_security import TransportSecuritySettings
from revenueflow.config import get_settings
from revenueflow.mcp.auth import bearer_gate
from revenueflow.mcp.server import lifespan, register_read_tools

# FastMCP defaults `host` to "127.0.0.1" and, when unset, auto-enables DNS
# rebinding protection with an allowed_hosts list of only localhost/127.0.0.1
# — every real Host header (the Cloud Run `.run.app` URL or the custom
# domain) then fails with 421 "Invalid Host header". The bearer token in
# `bearer_gate`, not the Host header, is this service's actual trust
# boundary (ADR-067) — same model as `/internal/*` — so disable it here
# instead of hardcoding a host allowlist that would break on any new domain.
mcp = FastMCP(
    "revenueflow-readonly",
    lifespan=lifespan,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
register_read_tools(mcp)

app = bearer_gate(mcp.streamable_http_app(), get_settings().mcp_api_token)
