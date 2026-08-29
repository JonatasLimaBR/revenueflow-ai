"""WhatsApp Cloud API inbound adapter.

Verifies the ``X-Hub-Signature-256`` HMAC and parses the webhook envelope down
to the text messages RevenueFlow cares about. Status callbacks and non-text
message types are ignored.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from revenueflow.domain.errors import ChannelError
from revenueflow.domain.models import NormalizedEvent


def verify_signature(raw: bytes, signature_header: str, app_secret: str) -> bool:
    """Return whether ``signature_header`` matches the HMAC of ``raw``."""

    if app_secret == "":
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_inbound(raw: bytes) -> list[NormalizedEvent]:
    """Parse a WhatsApp Cloud API webhook body into normalized text events."""

    try:
        body = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ChannelError("invalid whatsapp webhook payload") from exc

    if not isinstance(body, dict):
        raise ChannelError("invalid whatsapp webhook payload")

    events: list[NormalizedEvent] = []
    try:
        for entry in body["entry"]:
            for change in entry["changes"]:
                messages = change["value"].get("messages")
                if messages is None:
                    continue
                for message in messages:
                    event = _parse_message(message)
                    if event is not None:
                        events.append(event)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ChannelError("malformed whatsapp webhook payload") from exc

    return events


def _parse_message(message: dict[str, object]) -> NormalizedEvent | None:
    if message["type"] != "text":
        return None
    text = message["text"]
    if not isinstance(text, dict):
        raise ChannelError("malformed whatsapp text message")
    occurred_at = datetime.fromtimestamp(int(str(message["timestamp"])), tz=UTC)
    return NormalizedEvent(
        event_id=str(message["id"]),
        occurred_at=occurred_at,
        phone=str(message["from"]),
        message_id=str(message["id"]),
        message_type="text",
        message_text=str(text["body"]),
    )


class WhatsAppInbound:
    """``ChannelInbound`` backed by :func:`parse_inbound`."""

    def parse(self, raw: bytes) -> list[NormalizedEvent]:
        return parse_inbound(raw)
