"""Event publisher port and its implementations.

The default publisher is ``InMemoryPublisher`` and runs on the standard library
alone. ``PubSubPublisher`` imports ``google.cloud.pubsub_v1`` lazily inside
``__init__`` so importing this module never requires the optional ``events``
extra. Real Pub/Sub wiring lands in a later increment; ``_default_publisher``
keeps returning the in-memory implementation for now.
"""

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar, Token
from typing import Protocol, runtime_checkable

from revenueflow.config import get_settings
from revenueflow.domain.errors import ChannelError
from revenueflow.events.envelope import EventEnvelope, to_json

_LOGGER = logging.getLogger(__name__)


@runtime_checkable
class EventPublisher(Protocol):
    """Port used to hand a domain event to a transport."""

    async def publish(self, topic: str, envelope: EventEnvelope) -> None: ...


class InMemoryPublisher:
    """Publisher that records every envelope in a list for inspection."""

    def __init__(self) -> None:
        self.published: list[tuple[str, EventEnvelope]] = []

    async def publish(self, topic: str, envelope: EventEnvelope) -> None:
        self.published.append((topic, envelope))

    def clear(self) -> None:
        self.published.clear()


class PubSubPublisher:
    """Publisher that writes envelopes to Google Cloud Pub/Sub."""

    def __init__(self) -> None:
        from google.cloud import pubsub_v1

        self._client = pubsub_v1.PublisherClient()
        self._project_id = get_settings().pubsub_project_id

    def _topic_path(self, topic: str) -> str:
        return f"projects/{self._project_id}/topics/{topic}"

    async def publish(self, topic: str, envelope: EventEnvelope) -> None:
        data = to_json(envelope).encode()
        loop = asyncio.get_running_loop()
        try:
            future = self._client.publish(self._topic_path(topic), data=data)
            await loop.run_in_executor(None, future.result)
        except Exception as exc:
            _LOGGER.error("pubsub publish to %s failed", topic, exc_info=True)
            raise ChannelError("pubsub publish failed") from exc


_publisher: ContextVar[EventPublisher | None] = ContextVar("revenueflow_publisher", default=None)


def _default_publisher() -> EventPublisher:
    settings = get_settings()
    if settings.pubsub_emulator_host or settings.pubsub_project_id != "revenueflow-local":
        return InMemoryPublisher()
    return InMemoryPublisher()


def get_publisher() -> EventPublisher:
    current = _publisher.get()
    if current is not None:
        return current
    return _default_publisher()


def set_publisher(publisher: EventPublisher) -> Token[EventPublisher | None]:
    return _publisher.set(publisher)


def reset_publisher(token: Token[EventPublisher | None]) -> None:
    _publisher.reset(token)
