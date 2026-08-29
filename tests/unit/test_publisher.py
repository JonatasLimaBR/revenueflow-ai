from revenueflow.events import (
    EventPublisher,
    InMemoryPublisher,
    get_publisher,
    make_envelope,
    reset_publisher,
    set_publisher,
)


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
