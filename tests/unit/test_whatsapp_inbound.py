import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest

from revenueflow.adapters import parse_inbound, verify_signature
from revenueflow.domain.errors import ChannelError

_APP_SECRET = "top-secret"
_TIMESTAMP = 1_756_468_800


def _text_payload() -> bytes:
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "wba-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "pnid-1"},
                            "contacts": [{"wa_id": "5511999998888"}],
                            "messages": [
                                {
                                    "id": "wamid.ABC123",
                                    "from": "5511999998888",
                                    "timestamp": str(_TIMESTAMP),
                                    "type": "text",
                                    "text": {"body": "Ola, quero um plano"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    return json.dumps(body).encode()


def _status_payload() -> bytes:
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "wba-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "pnid-1"},
                            "statuses": [
                                {
                                    "id": "wamid.ABC123",
                                    "status": "delivered",
                                    "timestamp": str(_TIMESTAMP),
                                    "recipient_id": "5511999998888",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    return json.dumps(body).encode()


def test_verify_signature_true_for_correct_hmac() -> None:
    raw = _text_payload()
    digest = hmac.new(_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()

    assert verify_signature(raw, f"sha256={digest}", _APP_SECRET) is True


def test_verify_signature_false_for_wrong_hmac() -> None:
    raw = _text_payload()

    assert verify_signature(raw, "sha256=deadbeef", _APP_SECRET) is False


def test_verify_signature_false_for_empty_secret() -> None:
    raw = _text_payload()
    digest = hmac.new(b"", raw, hashlib.sha256).hexdigest()

    assert verify_signature(raw, f"sha256={digest}", "") is False


def test_parse_inbound_returns_single_normalized_event() -> None:
    events = parse_inbound(_text_payload())

    assert len(events) == 1
    event = events[0]
    assert event.phone == "5511999998888"
    assert event.message_id == "wamid.ABC123"
    assert event.event_id == "wamid.ABC123"
    assert event.message_type == "text"
    assert event.message_text == "Ola, quero um plano"
    assert event.occurred_at == datetime.fromtimestamp(_TIMESTAMP, tz=UTC)
    assert event.occurred_at.tzinfo is UTC


def test_parse_inbound_ignores_status_only_payload() -> None:
    assert parse_inbound(_status_payload()) == []


def test_parse_inbound_rejects_malformed_bytes() -> None:
    with pytest.raises(ChannelError):
        parse_inbound(b"not json")


def test_parse_inbound_rejects_missing_keys() -> None:
    broken = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"type": "text"}]}}]}]})
    with pytest.raises(ChannelError):
        parse_inbound(broken.encode())
