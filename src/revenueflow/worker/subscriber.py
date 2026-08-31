"""Production Pub/Sub pull loop for the message consumer.

This module is never imported by the test suite or CI. It is the deployment
entrypoint that binds the ``revenueflow.messages`` subscription to
:func:`process_event`. ``google.cloud.pubsub_v1`` is imported lazily so the rest
of the package keeps running without the optional ``events`` extra.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from revenueflow.config import get_settings
from revenueflow.events.envelope import from_json
from revenueflow.worker.consume import process_event

_LOGGER = logging.getLogger(__name__)

_SUBSCRIPTION = "revenueflow.messages"


async def run_subscriber() -> None:
    """Stream messages from the subscription and process each one exactly once."""

    from google.cloud import pubsub_v1

    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(settings.pubsub_project_id, _SUBSCRIPTION)
    loop = asyncio.get_running_loop()

    def _handle(message: Any) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(process_event(from_json(message.data)), loop)
            future.result()
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
