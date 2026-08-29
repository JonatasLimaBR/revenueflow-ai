"""In-memory outbound adapter and the outbound factory.

``FakeOutbound`` is the default so the platform runs without contacting the
WhatsApp Graph API. ``get_outbound`` returns the real adapter only when
``channel_outbound`` is set to ``"real"``.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from revenueflow.adapters.channel import ChannelOutbound
from revenueflow.adapters.whatsapp_outbound import WhatsAppOutbound
from revenueflow.config import get_settings


class FakeOutbound:
    """``ChannelOutbound`` that records every send for inspection."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, phone: str, text: str, dispatch_key: str) -> None:
        self.sent.append({"phone": phone, "text": text, "dispatch_key": dispatch_key})

    def clear(self) -> None:
        self.sent.clear()


_outbound: ContextVar[ChannelOutbound | None] = ContextVar("revenueflow_outbound", default=None)


def get_outbound() -> ChannelOutbound:
    current = _outbound.get()
    if current is not None:
        return current
    if get_settings().channel_outbound == "real":
        return WhatsAppOutbound()
    return FakeOutbound()


def set_outbound(outbound: ChannelOutbound) -> Token[ChannelOutbound | None]:
    return _outbound.set(outbound)


def reset_outbound(token: Token[ChannelOutbound | None]) -> None:
    _outbound.reset(token)
