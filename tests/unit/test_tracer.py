import pytest

from revenueflow.config import get_settings
from revenueflow.observability import (
    NoopTracer,
    Tracer,
    Usage,
    get_tracer,
    new_tracer,
    reset_tracer,
    set_tracer,
)
from revenueflow.observability.tracer import AuditTracer, LangfuseTracer


def test_noop_span_accepts_pii_attrs() -> None:
    tracer = NoopTracer()
    with tracer.span("node", attrs={"phone": "+5511999999999"}):
        pass


def test_noop_generation_round_trips() -> None:
    tracer = NoopTracer()
    with tracer.generation("call", model="gemini-2.0-flash", prompt_version="v1") as gen:
        gen.update(output={"x": 1}, usage=Usage(10, 20), cost_usd=0.001)
        gen.end()


def test_noop_event_and_end_do_not_raise() -> None:
    tracer = NoopTracer()
    tracer.event("thinking", attrs={"email": "a@b.com"})
    tracer.end(outcome="ok")


def test_noop_trace_id_is_non_empty_str() -> None:
    tracer = NoopTracer()
    assert isinstance(tracer.trace_id, str)
    assert tracer.trace_id


def test_noop_trace_id_uses_turn_id_when_given() -> None:
    tracer = NoopTracer(turn_id="turn-123")
    assert tracer.trace_id == "turn-123"


def test_new_tracer_wraps_in_audit_by_default() -> None:
    tracer = new_tracer(conversation_id="conv-1", turn_id="turn-1")
    assert isinstance(tracer, AuditTracer)
    assert isinstance(tracer._primary, NoopTracer)
    assert tracer.trace_id == "turn-1"


def test_audit_disabled_returns_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_ENABLED", "false")
    get_settings.cache_clear()
    try:
        tracer = new_tracer(conversation_id="conv-1", turn_id="turn-1")
        assert isinstance(tracer, NoopTracer)
    finally:
        get_settings.cache_clear()


async def test_langfuse_tracer_flush_calls_the_sdk_client_flush() -> None:
    # Found live (2026-09-09): `flush()` used to be a bare `return None`, so
    # the SDK's internal event queue was never explicitly sent -- a fresh
    # client per turn plus Cloud Run's default CPU-only-during-request model
    # meant the SDK's own background sender rarely got a chance to run
    # before the client was abandoned, and traces never reached the server.
    # `Langfuse.flush()` is documented as synchronous/blocking by design.
    calls: list[bool] = []

    class _FakeClient:
        def flush(self) -> None:
            calls.append(True)

    tracer = object.__new__(LangfuseTracer)
    tracer._client = _FakeClient()  # type: ignore[attr-defined]

    await tracer.flush()

    assert calls == [True]


async def test_langfuse_tracer_flush_swallows_client_errors() -> None:
    class _BoomClient:
        def flush(self) -> None:
            raise RuntimeError("langfuse down")

    tracer = object.__new__(LangfuseTracer)
    tracer._client = _BoomClient()  # type: ignore[attr-defined]

    await tracer.flush()  # must not raise


async def test_langfuse_tracer_flush_times_out_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from revenueflow.observability import tracer as tracer_module

    monkeypatch.setattr(tracer_module, "_LANGFUSE_FLUSH_TIMEOUT_S", 0.05)

    class _SlowClient:
        def flush(self) -> None:
            import time

            time.sleep(1)

    tracer = object.__new__(LangfuseTracer)
    tracer._client = _SlowClient()  # type: ignore[attr-defined]

    await tracer.flush()  # must not raise even though the call times out


def test_get_set_reset_tracer() -> None:
    original = get_tracer()
    assert isinstance(original, Tracer)
    replacement = NoopTracer(turn_id="swapped")
    token = set_tracer(replacement)
    try:
        assert get_tracer() is replacement
    finally:
        reset_tracer(token)
    assert get_tracer() is original
