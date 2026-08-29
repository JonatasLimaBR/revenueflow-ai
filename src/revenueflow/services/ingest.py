"""Inbound message ingestion service.

``ingest_message`` claims the provider message id for exactly-once processing
and publishes a ``message_received`` event inside the same unit of work, so a
commit failure drops the claim and the provider can safely redeliver.

The WhatsApp webhook contract requires this call to never raise: any unexpected
failure is logged and reported as ``False`` (not accepted), which lets the
caller return a non-2xx and have the message redelivered later.
"""

from __future__ import annotations

import logging

from revenueflow.domain.models import NormalizedEvent
from revenueflow.events import get_publisher, make_envelope
from revenueflow.observability import get_tracer
from revenueflow.repositories import processed_event
from revenueflow.repositories.db import unit_of_work

_LOGGER = logging.getLogger(__name__)


async def ingest_message(event: NormalizedEvent, *, topic: str = "revenueflow.messages") -> bool:
    """Accept an inbound message once and publish it; return whether it was accepted."""

    tracer = get_tracer()
    try:
        with tracer.span("ingest", attrs={"message_id": event.message_id}):
            async with unit_of_work() as conn:
                claimed = await processed_event.claim(conn, kind="inbound", key=event.message_id)
                if not claimed:
                    return False
                payload = {
                    "event_id": event.event_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "phone": event.phone,
                    "message_id": event.message_id,
                    "message_type": event.message_type,
                    "message_text": event.message_text,
                }
                envelope = make_envelope("message_received", payload, trace_id=tracer.trace_id)
                await get_publisher().publish(topic, envelope)
        return True
    except Exception:
        _LOGGER.exception("ingest_message failed for %s", event.message_id)
        return False
