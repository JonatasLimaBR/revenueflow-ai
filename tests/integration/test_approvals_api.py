from decimal import Decimal
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revenueflow.config import get_settings
from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.events import InMemoryPublisher
from revenueflow.main import app
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work


def _pending(conversation_id: str) -> Approval:
    return Approval(
        approval_id=uuid4().hex,
        conversation_id=conversation_id,
        turn_id=f"t-{uuid4().hex}",
        reason="discount_out_of_policy",
        requested_discount=Decimal("0.25"),
        current_margin=Decimal("0.3000"),
        resulting_margin=Decimal("0.0800"),
        amount=Decimal("1000.00"),
        customer_ref="CUST-9",
        status=ApprovalStatus.PENDING,
    )


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_missing_or_bad_bearer_401(db: None, approval_settings: str) -> None:
    async with LifespanManager(app), await _client() as client:
        no_header = await client.post("/internal/approvals/x", json={"decision": "reject"})
        bad = await client.post(
            "/internal/approvals/x",
            json={"decision": "reject"},
            headers={"Authorization": "Bearer nope"},
        )
    assert no_header.status_code == 401
    assert bad.status_code == 401


async def test_no_token_configured_503(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPROVAL_API_TOKEN", raising=False)
    get_settings.cache_clear()
    async with LifespanManager(app), await _client() as client:
        resp = await client.get("/internal/approvals", headers={"Authorization": "Bearer whatever"})
    get_settings.cache_clear()
    assert resp.status_code == 503


async def test_override_without_pct_422(db: None, approval_settings: str) -> None:
    async with LifespanManager(app), await _client() as client:
        resp = await client.post(
            "/internal/approvals/x",
            json={"decision": "approve_with_override"},
            headers={"Authorization": f"Bearer {approval_settings}"},
        )
    assert resp.status_code == 422


async def test_bad_decision_422(db: None, approval_settings: str) -> None:
    async with LifespanManager(app), await _client() as client:
        resp = await client.post(
            "/internal/approvals/x",
            json={"decision": "maybe"},
            headers={"Authorization": f"Bearer {approval_settings}"},
        )
    assert resp.status_code == 422


async def test_unknown_approval_404(db: None, approval_settings: str) -> None:
    async with LifespanManager(app), await _client() as client:
        resp = await client.post(
            "/internal/approvals/does-not-exist",
            json={"decision": "reject"},
            headers={"Authorization": f"Bearer {approval_settings}"},
        )
    assert resp.status_code == 404


async def test_approve_transitions_and_publishes_once_then_noop(
    db: None, approval_settings: str, publisher: InMemoryPublisher
) -> None:
    approval = _pending(f"c-{uuid4().hex}")
    async with unit_of_work() as conn:
        await approval_repo.create_pending(conn, approval)

    headers = {"Authorization": f"Bearer {approval_settings}"}
    async with LifespanManager(app), await _client() as client:
        first = await client.post(
            f"/internal/approvals/{approval.approval_id}",
            json={"decision": "approve"},
            headers=headers,
        )
        second = await client.post(
            f"/internal/approvals/{approval.approval_id}",
            json={"decision": "approve"},
            headers=headers,
        )

        assert first.status_code == 200
        assert first.json() == {"published": True, "status": "APPROVED"}
        assert second.status_code == 200
        assert second.json()["published"] is False

        decided = [e for _, e in publisher.published if e.event_type == "approval_decided"]
        assert len(decided) == 1
        assert decided[0].payload["approval_id"] == approval.approval_id
        assert decided[0].payload["decision"] == "approve"

        async with unit_of_work() as conn:
            stored = await approval_repo.get(conn, approval.approval_id)
    assert stored is not None
    assert stored.status is ApprovalStatus.APPROVED
    assert stored.decided_at is not None


async def test_list_pending_returns_open_approvals(db: None, approval_settings: str) -> None:
    approval = _pending(f"c-{uuid4().hex}")
    async with unit_of_work() as conn:
        await approval_repo.create_pending(conn, approval)
    async with LifespanManager(app), await _client() as client:
        resp = await client.get(
            "/internal/approvals?status=PENDING",
            headers={"Authorization": f"Bearer {approval_settings}"},
        )
    assert resp.status_code == 200
    ids = [row["approval_id"] for row in resp.json()]
    assert approval.approval_id in ids
