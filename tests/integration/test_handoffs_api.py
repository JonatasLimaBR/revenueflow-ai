from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revenueflow.config import get_settings
from revenueflow.domain.models import HandoffReason
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories.db import unit_of_work


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test")


def _app() -> object:
    from revenueflow.main import app

    return app


async def test_missing_or_bad_bearer_401(db: None, handoff_settings: str) -> None:
    async with LifespanManager(_app()), await _client() as client:
        no_header = await client.get("/internal/handoffs")
        bad = await client.get("/internal/handoffs", headers={"Authorization": "Bearer nope"})
    assert no_header.status_code == 401
    assert bad.status_code == 401


async def test_no_token_configured_503(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HANDOFF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    async with LifespanManager(_app()), await _client() as client:
        resp = await client.get("/internal/handoffs", headers={"Authorization": "Bearer whatever"})
    get_settings.cache_clear()
    assert resp.status_code == 503


async def test_list_pending_then_resolve(db: None, handoff_settings: str) -> None:
    conversation_id = f"c-{uuid4().hex}"
    async with unit_of_work() as conn:
        created = await handoff_repo.create(
            conn, conversation_id, HandoffReason.EXPLICIT_REQUEST, {"reason": "explicit_request"}
        )
    auth = {"Authorization": f"Bearer {handoff_settings}"}

    async with LifespanManager(_app()), await _client() as client:
        listed = await client.get("/internal/handoffs", headers=auth)
        first = await client.post(f"/internal/handoffs/{created.handoff_id}", headers=auth)
        second = await client.post(f"/internal/handoffs/{created.handoff_id}", headers=auth)
        after = await client.get("/internal/handoffs", headers=auth)

    ids = {row["handoff_id"] for row in listed.json()}
    assert created.handoff_id in ids
    assert first.json() == {"status": "resolved"}
    assert second.json() == {"status": "noop"}
    assert created.handoff_id not in {row["handoff_id"] for row in after.json()}
