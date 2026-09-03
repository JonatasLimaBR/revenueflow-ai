from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from revenueflow.domain.models import AuditEvent
from revenueflow.services import audit as audit_svc


def _event() -> AuditEvent:
    return AuditEvent(
        audit_id="t-err",
        trace_id="trace-err",
        conversation_id="c-err",
        turn_id="t-err",
        agent="recommendation",
        model=None,
        prompt_version=None,
        outcome="replied",
        policy_decision="n/a",
        handoff=False,
        tools=[],
        token_usage=0,
        cost_usd=Decimal("0"),
        latency_ms=12,
        events=[],
        created_at=datetime.now(UTC),
    )


async def test_persist_swallows_repo_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    @asynccontextmanager
    async def _fake_uow() -> Any:
        yield object()

    async def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("revenueflow.services.audit.unit_of_work", _fake_uow)
    monkeypatch.setattr("revenueflow.services.audit.audit_repo.record", _boom)

    with caplog.at_level("ERROR"):
        await audit_svc.persist(_event())

    assert "audit persist failed" in caplog.text
    assert "trace-err" in caplog.text
