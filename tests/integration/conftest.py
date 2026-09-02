"""Shared fixtures for the webhook and consumer integration tests.

Everything the test modules need is exposed as a fixture so no test has to
import from this module (``tests`` is not an importable package).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Iterator

import pytest

from revenueflow.config import get_settings
from revenueflow.events import InMemoryPublisher, reset_publisher, set_publisher

_APP_SECRET = "test-app-secret"
_VERIFY_TOKEN = "test-verify-token"

SignedWebhook = Callable[[str], tuple[bytes, str]]


def _text_payload(text: str) -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "pnid-1"},
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.TEST1",
                                    "timestamp": "1724930000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _sign(body: bytes) -> str:
    digest = hmac.new(_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def whatsapp_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Point ``get_settings`` at known credentials; yield the verify token."""

    monkeypatch.setenv("WHATSAPP_APP_SECRET", _APP_SECRET)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", _VERIFY_TOKEN)
    get_settings.cache_clear()
    yield _VERIFY_TOKEN
    get_settings.cache_clear()


@pytest.fixture
def approval_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Set a known ``APPROVAL_API_TOKEN``; yield it."""

    token = "test-approval-token"
    monkeypatch.setenv("APPROVAL_API_TOKEN", token)
    get_settings.cache_clear()
    yield token
    get_settings.cache_clear()


@pytest.fixture
def publisher() -> Iterator[InMemoryPublisher]:
    """Install an ``InMemoryPublisher`` for the duration of the test."""

    recorder = InMemoryPublisher()
    token = set_publisher(recorder)
    try:
        yield recorder
    finally:
        reset_publisher(token)


@pytest.fixture
def signed_webhook() -> SignedWebhook:
    """Return a factory: ``text -> (raw_body, x_hub_signature_256)``."""

    def _make(text: str = "quero uma bomba d'agua 1cv") -> tuple[bytes, str]:
        body = json.dumps(_text_payload(text)).encode()
        return body, _sign(body)

    return _make
