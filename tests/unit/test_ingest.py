from datetime import UTC, datetime

from revenueflow.domain.models import NormalizedEvent
from revenueflow.events import InMemoryPublisher, reset_publisher, set_publisher
from revenueflow.services import ingest_message


def _event(message_id: str) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=message_id,
        occurred_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        phone="+5511900000010",
        message_id=message_id,
        message_type="text",
        message_text="ola, quero uma bomba",
    )


async def test_ingest_message_publishes_once_and_dedupes(db: None) -> None:
    publisher = InMemoryPublisher()
    token = set_publisher(publisher)
    try:
        first = await ingest_message(_event("wamid.1"))
        assert first is True
        assert len(publisher.published) == 1
        topic, envelope = publisher.published[0]
        assert topic == "revenueflow.messages"
        assert envelope.event_type == "message_received"
        assert envelope.payload["message_id"] == "wamid.1"

        duplicate = await ingest_message(_event("wamid.1"))
        assert duplicate is False
        assert len(publisher.published) == 1

        other = await ingest_message(_event("wamid.2"))
        assert other is True
        assert len(publisher.published) == 2
    finally:
        reset_publisher(token)
