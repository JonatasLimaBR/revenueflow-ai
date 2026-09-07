"""Regression test for the FastMCP Host-header rejection bug (ADR-067 follow-up).

``mcp/http_server.py`` needs the optional ``mcp`` extra to import (not
installed in the base ``tests`` CI job — see pyproject.toml), so this checks
the source text directly rather than importing the module. See the module's
own inline comment for why: FastMCP defaults `host` to "127.0.0.1" and, when
`transport_security` is left unset, auto-enables DNS rebinding protection
with an allowed_hosts list of only localhost/127.0.0.1 — silently rejecting
every real Host header (Cloud Run `.run.app` URL or a custom domain) with
421 "Invalid Host header". Confirmed live in production (2026-09-07): the
public read-only MCP server never answered a single real request since its
ADR-067 deploy.
"""

from pathlib import Path

_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "revenueflow" / "mcp" / "http_server.py"
).read_text()


def test_transport_security_is_explicitly_configured() -> None:
    assert "transport_security=TransportSecuritySettings(" in _SOURCE


def test_dns_rebinding_protection_is_disabled() -> None:
    assert "enable_dns_rebinding_protection=False" in _SOURCE
