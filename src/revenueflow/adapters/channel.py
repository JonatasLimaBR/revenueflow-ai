"""Channel adapter ports.

``ChannelInbound`` turns a raw webhook body into normalized domain events;
``ChannelOutbound`` delivers a reply back to the customer. Implementations live
alongside this module.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from revenueflow.domain.models import NormalizedEvent


@runtime_checkable
class ChannelInbound(Protocol):
    """Port that parses an inbound channel payload into domain events."""

    def parse(self, raw: bytes) -> list[NormalizedEvent]: ...


@runtime_checkable
class ChannelOutbound(Protocol):
    """Port that sends a single text reply to a phone number."""

    async def send(self, *, phone: str, text: str, dispatch_key: str) -> None: ...
