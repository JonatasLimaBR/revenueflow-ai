import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import pytest

from revenueflow.domain.models import AuditEvent
from revenueflow.observability.tracer import AuditTracer, Usage

_LOG_FIELDS = {
    "conversation_id",
    "outcome",
    "agent",
    "model",
    "cost_usd",
    "token_usage",
    "latency_ms",
    "handoff",
    "tool_failures",
}


class _SpySpan:
    def __init__(self, calls: list[str], name: str) -> None:
        self._calls = calls
        self._name = name

    def end(self) -> None:
        self._calls.append(f"span.end:{self._name}")


class _SpyGeneration:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def update(self, **_kw: Any) -> None:
        self._calls.append("gen.update")

    def end(self) -> None:
        self._calls.append("gen.end")


class _SpyPrimary:
    def __init__(self) -> None:
        self.trace_id = "spy-trace"
        self.calls: list[str] = []

    @contextmanager
    def span(self, name: str, *, attrs: Any = None) -> Iterator[_SpySpan]:
        self.calls.append(f"span:{name}")
        yield _SpySpan(self.calls, name)

    @contextmanager
    def generation(
        self, name: str, *, model: str, prompt_version: str, input: Any = None
    ) -> Iterator[_SpyGeneration]:
        self.calls.append(f"generation:{name}:{model}")
        yield _SpyGeneration(self.calls)

    def event(self, name: str, *, attrs: Any = None) -> None:
        self.calls.append(f"event:{name}")

    def end(self, *, outcome: str, policy_decision: str = "n/a", handoff: bool = False) -> None:
        self.calls.append(f"end:{outcome}")

    async def flush(self) -> None:
        return None


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[AuditEvent]:
    box: list[AuditEvent] = []

    async def _persist(event: AuditEvent) -> None:
        box.append(event)

    monkeypatch.setattr("revenueflow.services.audit.persist", _persist)
    return box


def _tracer(primary: _SpyPrimary) -> AuditTracer:
    return AuditTracer(primary, conversation_id="c-1", turn_id="t-1")


async def test_buffer_to_row_and_delegation(captured: list[AuditEvent]) -> None:
    spy = _SpyPrimary()
    t = _tracer(spy)

    with t.span("tool.a"):
        pass
    with t.generation("g", model="gemini-2.5-flash", prompt_version="v2") as gen:
        gen.update(usage=Usage(10, 20), cost_usd=0.001)
    with t.span("tool.b"):
        pass
    with t.span("node.recommendation"):
        pass
    t.end(outcome="replied")
    await t.flush()

    assert "span:tool.a" in spy.calls
    assert any(c.startswith("generation:g:gemini-2.5-flash") for c in spy.calls)
    assert "gen.update" in spy.calls
    assert "end:replied" in spy.calls

    row = captured[0]
    assert row.audit_id == "t-1"
    assert row.trace_id == "spy-trace"
    assert row.conversation_id == "c-1"
    assert row.tools == ["tool.a", "tool.b"]
    assert row.token_usage == 30
    assert row.cost_usd == Decimal("0.001")
    assert row.model == "gemini-2.5-flash"
    assert row.prompt_version == "v2"
    assert row.agent == "recommendation"
    assert row.outcome == "replied"
    assert [e["kind"] for e in row.events] == ["span", "generation", "span", "span"]


async def test_row_without_generation(captured: list[AuditEvent]) -> None:
    t = _tracer(_SpyPrimary())
    with t.span("tool.x"):
        pass
    t.end(outcome="quoted")
    await t.flush()

    row = captured[0]
    assert row.model is None
    assert row.prompt_version is None
    assert row.token_usage == 0
    assert row.cost_usd == Decimal("0")


async def test_latency_is_measured(captured: list[AuditEvent]) -> None:
    t = _tracer(_SpyPrimary())
    await asyncio.sleep(0.05)
    t.end(outcome="replied")
    await t.flush()

    row = captured[0]
    assert isinstance(row.latency_ms, int)
    assert 30 <= row.latency_ms <= 500


async def test_flush_is_idempotent(captured: list[AuditEvent]) -> None:
    t = _tracer(_SpyPrimary())
    t.end(outcome="replied")
    await t.flush()
    await t.flush()
    assert len(captured) == 1


async def test_span_attrs_are_masked(captured: list[AuditEvent]) -> None:
    t = _tracer(_SpyPrimary())
    with t.span("node.x", attrs={"phone": "5511999999999"}):
        pass
    t.end(outcome="replied")
    await t.flush()

    entry = next(e for e in captured[0].events if e["name"] == "node.x")
    assert "5511999999999" not in str(entry.get("attrs"))


async def test_delegates_event(captured: list[AuditEvent]) -> None:
    spy = _SpyPrimary()
    t = _tracer(spy)
    t.event("negotiation.policy", attrs={"reason": "ok"})
    t.end(outcome="replied")
    await t.flush()
    assert "event:negotiation.policy" in spy.calls


async def test_audit_turn_log_line_has_expected_fields(
    captured: list[AuditEvent], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="revenueflow.observability.tracer")
    t = _tracer(_SpyPrimary())
    with t.span("tool.a"):
        pass
    with t.generation("g", model="gemini-2.5-flash", prompt_version="v2") as gen:
        gen.update(usage=Usage(10, 20), cost_usd=0.001)
    with t.span("node.recommendation"):
        pass
    t.end(outcome="replied")
    await t.flush()

    record = next(r for r in caplog.records if r.message == "audit.turn")
    assert set(_LOG_FIELDS) <= set(record.__dict__)
    assert record.conversation_id == "c-1"
    assert record.outcome == "replied"
    assert record.agent == "recommendation"
    assert record.model == "gemini-2.5-flash"
    assert record.cost_usd == pytest.approx(0.001)
    assert record.token_usage == 30
    assert record.handoff is False
    assert record.tool_failures == 0


async def test_log_line_keys_are_allowlisted(
    captured: list[AuditEvent], caplog: pytest.LogCaptureFixture
) -> None:
    from revenueflow.observability.logging_setup import _RESERVED

    caplog.set_level(logging.INFO, logger="revenueflow.observability.tracer")
    t = _tracer(_SpyPrimary())
    t.end(outcome="replied")
    await t.flush()

    record = next(r for r in caplog.records if r.message == "audit.turn")
    extra = {k for k in record.__dict__ if k not in _RESERVED and not k.startswith("_")}
    assert extra == _LOG_FIELDS


async def test_tool_failures_counts_propagated_exceptions(
    captured: list[AuditEvent], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="revenueflow.observability.tracer")
    t = _tracer(_SpyPrimary())
    with t.span("tool.ok"):
        pass
    with pytest.raises(RuntimeError):
        with t.span("tool.boom"):
            raise RuntimeError("boom")
    t.end(outcome="error")
    await t.flush()

    record = next(r for r in caplog.records if r.message == "audit.turn")
    assert record.tool_failures == 1
    boom = next(e for e in captured[0].events if e["name"] == "tool.boom")
    assert boom.get("error") is True


async def test_log_failure_does_not_break_flush(
    captured: list[AuditEvent], monkeypatch: pytest.MonkeyPatch
) -> None:
    from revenueflow.observability import tracer as tracer_mod

    def _boom(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("logging is down")

    monkeypatch.setattr(tracer_mod._LOGGER, "info", _boom)
    t = _tracer(_SpyPrimary())
    t.end(outcome="replied")
    await t.flush()

    assert len(captured) == 1
