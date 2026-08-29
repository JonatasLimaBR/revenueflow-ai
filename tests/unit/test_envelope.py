from datetime import UTC, datetime

from revenueflow.events import EventEnvelope, make_envelope
from revenueflow.events.envelope import SCHEMA_VERSION, from_json, to_json


def test_make_envelope_fills_defaults() -> None:
    env = make_envelope("lead.created", {"lead_id": "l-1"}, trace_id="trace-1")

    assert env.event_type == "lead.created"
    assert env.trace_id == "trace-1"
    assert env.schema_version == SCHEMA_VERSION
    assert env.payload == {"lead_id": "l-1"}
    assert len(env.event_id) == 32
    assert env.occurred_at.tzinfo is not None


def test_make_envelope_copies_payload() -> None:
    source = {"a": 1}
    env = make_envelope("x", source, trace_id="t")
    source["a"] = 2

    assert env.payload == {"a": 1}


def test_make_envelope_honors_explicit_values() -> None:
    occurred_at = datetime(2026, 8, 29, 12, 30, tzinfo=UTC)
    env = make_envelope(
        "order.placed",
        {"order_id": "o-9"},
        trace_id="t-9",
        event_id="evt-9",
        occurred_at=occurred_at,
    )

    assert env.event_id == "evt-9"
    assert env.occurred_at == occurred_at


def test_json_round_trip_preserves_all_fields() -> None:
    occurred_at = datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=UTC)
    env = EventEnvelope(
        event_id="evt-1",
        event_type="lead.qualified",
        occurred_at=occurred_at,
        trace_id="trace-1",
        schema_version=SCHEMA_VERSION,
        payload={"score": 42, "tags": ["hot", "inbound"]},
    )

    restored = from_json(to_json(env))

    assert restored == env
    assert restored.occurred_at == occurred_at
    assert restored.occurred_at.tzinfo is not None


def test_from_json_accepts_bytes() -> None:
    env = make_envelope("ping", {"n": 1}, trace_id="t")

    restored = from_json(to_json(env).encode())

    assert restored == env
