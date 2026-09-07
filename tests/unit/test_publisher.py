import pytest

from revenueflow.config import get_settings
from revenueflow.events import (
    EventPublisher,
    InMemoryPublisher,
    get_publisher,
    make_envelope,
    reset_publisher,
    set_publisher,
)
from revenueflow.events import publisher as publisher_module


async def test_in_memory_publisher_records_topic_and_envelope() -> None:
    publisher = InMemoryPublisher()
    envelope = make_envelope("lead.created", {"lead_id": "l-1"}, trace_id="t-1")

    await publisher.publish("leads", envelope)

    assert publisher.published == [("leads", envelope)]


async def test_in_memory_publisher_clear() -> None:
    publisher = InMemoryPublisher()
    await publisher.publish("leads", make_envelope("x", {}, trace_id="t"))

    publisher.clear()

    assert publisher.published == []


def test_get_publisher_returns_event_publisher() -> None:
    assert isinstance(get_publisher(), EventPublisher)


def test_set_and_reset_publisher_swaps_and_restores() -> None:
    replacement = InMemoryPublisher()

    token = set_publisher(replacement)
    try:
        assert get_publisher() is replacement
    finally:
        reset_publisher(token)

    restored = get_publisher()
    assert restored is not replacement
    assert isinstance(restored, InMemoryPublisher)


def test_default_publisher_uses_pubsub_for_a_real_project_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: both branches of _default_publisher used to return
    InMemoryPublisher, so a real GCP project id (production) silently
    dropped every event instead of reaching the real Pub/Sub topic —
    found live, no inbound WhatsApp message had ever reached the graph."""

    class _FakePubSubPublisher:
        pass

    monkeypatch.setattr(publisher_module, "PubSubPublisher", _FakePubSubPublisher)
    monkeypatch.setenv("PUBSUB_PROJECT_ID", "revenueflow-ai-prod")
    get_settings.cache_clear()
    try:
        assert isinstance(publisher_module._default_publisher(), _FakePubSubPublisher)
    finally:
        get_settings.cache_clear()


def test_default_publisher_uses_in_memory_for_the_local_project_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBSUB_PROJECT_ID", "revenueflow-local")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "")
    get_settings.cache_clear()
    try:
        assert isinstance(publisher_module._default_publisher(), InMemoryPublisher)
    finally:
        get_settings.cache_clear()
