import pytest

from revenueflow.adapters import FakeOutbound, get_outbound, reset_outbound, set_outbound
from revenueflow.adapters.channel import ChannelOutbound
from revenueflow.adapters.whatsapp_outbound import WhatsAppOutbound
from revenueflow.config import get_settings


async def test_fake_outbound_records_send() -> None:
    outbound = FakeOutbound()

    await outbound.send(phone="5511999998888", text="oi", dispatch_key="d-1")

    assert outbound.sent == [{"phone": "5511999998888", "text": "oi", "dispatch_key": "d-1"}]


async def test_fake_outbound_clear() -> None:
    outbound = FakeOutbound()
    await outbound.send(phone="p", text="t", dispatch_key="d")

    outbound.clear()

    assert outbound.sent == []


def test_get_outbound_default_is_fake() -> None:
    assert isinstance(get_outbound(), FakeOutbound)


def test_set_and_reset_outbound_swaps_and_restores() -> None:
    replacement = FakeOutbound()

    token = set_outbound(replacement)
    try:
        assert get_outbound() is replacement
    finally:
        reset_outbound(token)

    assert get_outbound() is not replacement


def test_get_outbound_real_when_channel_outbound_is_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHANNEL_OUTBOUND", "real")
    get_settings.cache_clear()
    try:
        outbound: ChannelOutbound = get_outbound()
        assert isinstance(outbound, WhatsAppOutbound)
    finally:
        monkeypatch.delenv("CHANNEL_OUTBOUND", raising=False)
        get_settings.cache_clear()
