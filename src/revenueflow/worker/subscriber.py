"""Production Pub/Sub pull loop for the message consumer.

This module is never imported by the test suite or CI. It is the deployment
entrypoint that binds the ``revenueflow.messages`` subscription to
:func:`process_event`. ``google.cloud.pubsub_v1`` is imported lazily so the rest
of the package keeps running without the optional ``events`` extra.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from revenueflow.config import get_settings
from revenueflow.events.envelope import from_json
from revenueflow.worker.consume import process_approval_decided, process_event

_LOGGER = logging.getLogger(__name__)

_SUBSCRIPTION = "revenueflow.messages"

_ROUTES = {
    "message_received": process_event,
    "approval_decided": process_approval_decided,
}


async def run_subscriber() -> None:
    """Stream messages from the subscription and process each one exactly once."""

    from revenueflow.observability.logging_setup import configure_logging

    configure_logging()

    from google.cloud import pubsub_v1

    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(settings.pubsub_project_id, _SUBSCRIPTION)
    loop = asyncio.get_running_loop()

    def _handle(message: Any) -> None:
        # Diagnostic (temporary): pin down where a turn's time actually goes.
        # publish_time -> _handle is Pub/Sub delivery + client dispatch;
        # _handle -> scheduled is asyncio.run_coroutine_threadsafe queueing on
        # the event loop; the rest is process_event() itself (already partly
        # visible via the AFC/turn-budget logs). Multi-minute turns kept
        # recurring after 4 separate fixes (EventPublisher, Vertex client
        # cache, app DB pool, checkpointer pool) that all targeted
        # process_event()'s internals — this narrows down whether the delay
        # is actually upstream of it instead.
        try:
            received_at = time.monotonic()
            publish_time = getattr(message, "publish_time", None)
            _LOGGER.info(
                "pubsub message dispatched: message_id=%s publish_time=%s delivery_delay_s=%s",
                getattr(message, "message_id", None),
                publish_time,
                # time.time(), not received_at (time.monotonic() has no
                # relation to wall-clock/epoch time — mixing the two here
                # produced a nonsensical multi-billion-second delta live).
                (time.time() - publish_time.timestamp()) if publish_time else None,
            )
            envelope = from_json(message.data)
            handler = _ROUTES.get(envelope.event_type)
            if handler is None:
                _LOGGER.warning("unknown event_type %s; acking", envelope.event_type)
                message.ack()
                return
            scheduled_at = time.monotonic()
            _LOGGER.info(
                "scheduling handler on event loop: dispatch_to_schedule_s=%.3f",
                scheduled_at - received_at,
            )
            asyncio.run_coroutine_threadsafe(handler(envelope), loop).result()
            _LOGGER.info(
                "handler finished: message_id=%s total_s=%.3f",
                getattr(message, "message_id", None),
                time.monotonic() - received_at,
            )
        except Exception:
            _LOGGER.exception("consumer failed; nacking message")
            message.nack()
        else:
            message.ack()

    streaming_pull = subscriber.subscribe(subscription_path, callback=_handle)
    _LOGGER.info("subscriber listening on %s", subscription_path)
    try:
        await loop.run_in_executor(None, streaming_pull.result)
    except asyncio.CancelledError:
        streaming_pull.cancel()
        raise
    except Exception:
        streaming_pull.cancel()
        _LOGGER.exception("subscriber stream stopped")
        raise
