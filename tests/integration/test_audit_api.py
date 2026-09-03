from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revenueflow.config import get_settings
from revenueflow.repositories.db import execute, unit_of_work

_INSERT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, 'recommendation', NULL, NULL, %s, 'n/a', false,
    '["tool.search_products"]'::jsonb, %s, %s, 10, '[{"kind":"span","name":"node.x"}]'::jsonb)
"""


def _app() -> object:
    from revenueflow.main import app

    return app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test")


async def test_auth(db: None, handoff_settings: str) -> None:
    async with LifespanManager(_app()), await _client() as client:
        no_header = await client.get("/internal/audit/c-x")
        bad = await client.get("/internal/audit/c-x", headers={"Authorization": "Bearer nope"})
    assert no_header.status_code == 401
    assert bad.status_code == 401


async def test_no_token_configured_503(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HANDOFF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    async with LifespanManager(_app()), await _client() as client:
        resp = await client.get("/internal/audit/c-x", headers={"Authorization": "Bearer whatever"})
    get_settings.cache_clear()
    assert resp.status_code == 503


async def test_reconstruct_returns_turns_in_order(db: None, handoff_settings: str) -> None:
    conversation_id = f"c-{uuid4().hex}"
    async with unit_of_work() as conn:
        for i, tokens in enumerate((100, 200)):
            await execute(
                conn,
                _INSERT,
                (
                    f"{conversation_id}-{i}",
                    f"tr-{i}",
                    conversation_id,
                    f"{conversation_id}-{i}",
                    "replied",
                    tokens,
                    "0.001",
                ),
            )

    async with LifespanManager(_app()), await _client() as client:
        resp = await client.get(
            f"/internal/audit/{conversation_id}",
            headers={"Authorization": f"Bearer {handoff_settings}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["turn_id"] == f"{conversation_id}-0"
    assert body[0]["events"]
