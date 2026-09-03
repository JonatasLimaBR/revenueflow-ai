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
from revenueflow.observability.tracer import AuditTracer


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
