"""Renders portal pages against a bare test app (no lifespan, no real
pool) to verify: mask() is applied to any phone before it reaches a
template (SC3/ADR-058), and pages render without error when there is no
data yet (SC7 — zero conversations is the common case until the WhatsApp
webhook is registered)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from revenueflow.portal import auth, views
from revenueflow.repositories import analytics as analytics_repo
from revenueflow.repositories import portal as portal_repo


@asynccontextmanager
async def _fake_read_connection() -> Any:
    yield None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(views.router)
    app.dependency_overrides[views.get_session] = lambda: auth.Session(
        email="team@example.com", issued_at=0
    )
    monkeypatch.setattr(views, "read_connection", _fake_read_connection)
    return TestClient(app)


async def _empty(conn: object) -> list[dict[str, Any]]:
    return []


async def _zero_handoff_rate(conn: object) -> list[dict[str, Any]]:
    return [{"total_turns": 0, "handoff_turns": 0}]


def test_home_renders_without_error_on_empty_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(analytics_repo, "conversation_revenue", _empty)
    monkeypatch.setattr(analytics_repo, "cost_per_outcome", _empty)
    monkeypatch.setattr(analytics_repo, "handoff_rate", _zero_handoff_rate)

    response = client.get("/portal/")

    assert response.status_code == 200
    assert "Nenhuma conversa ainda" in response.text


def test_conversations_page_never_leaks_raw_phone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_phone = "+5511987654321"

    async def _rows(conn: object, *, limit: int = 50) -> list[dict[str, Any]]:
        return [
            {
                "conversation_id": "c1",
                "phone": raw_phone,
                "status": "OPEN",
                "current_intent": "RECOMMENDATION",
                "current_agent": "recommendation",
                "last_interaction": "2026-09-05T00:00:00",
                "customer_id": None,
            }
        ]

    monkeypatch.setattr(portal_repo, "recent_conversations", _rows)

    response = client.get("/portal/conversations")

    assert response.status_code == 200
    assert raw_phone not in response.text
    assert "***" in response.text


def test_conversations_page_renders_empty_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portal_repo, "recent_conversations", _empty)

    response = client.get("/portal/conversations")

    assert response.status_code == 200
    assert "Nenhuma conversa ainda" in response.text


def test_login_page_renders_without_google_client_id(client: TestClient) -> None:
    response = client.get("/portal/login")

    assert response.status_code == 200
    assert "não configurado" in response.text
