"""Immutable event envelope and its JSON codec.

Every event RevenueFlow publishes is wrapped in an ``EventEnvelope`` so that
consumers get a stable identity, a schema version, and the originating trace id
regardless of the payload shape.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import uuid4

SCHEMA_VERSION: Final[int] = 1


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """A single domain event ready to be published to a topic."""

    event_id: str
    event_type: str
    occurred_at: datetime
    trace_id: str
    schema_version: int
    payload: dict[str, Any]


def make_envelope(
    event_type: str,
    payload: Mapping[str, Any],
    *,
    trace_id: str,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    """Build an envelope, filling in id, timestamp, and schema version."""

    return EventEnvelope(
        event_id=event_id or uuid4().hex,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(UTC),
        trace_id=trace_id,
        schema_version=SCHEMA_VERSION,
        payload=dict(payload),
    )


def to_json(env: EventEnvelope) -> str:
    """Serialize an envelope to a compact JSON string."""

    return json.dumps(
        {
            "event_id": env.event_id,
            "event_type": env.event_type,
            "occurred_at": env.occurred_at.isoformat(),
            "trace_id": env.trace_id,
            "schema_version": env.schema_version,
            "payload": env.payload,
        }
    )


def from_json(raw: str | bytes) -> EventEnvelope:
    """Parse a JSON string or bytes back into an envelope."""

    data = json.loads(raw)
    return EventEnvelope(
        event_id=data["event_id"],
        event_type=data["event_type"],
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        trace_id=data["trace_id"],
        schema_version=int(data["schema_version"]),
        payload=dict(data["payload"]),
    )
