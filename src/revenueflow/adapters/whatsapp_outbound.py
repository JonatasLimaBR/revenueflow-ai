"""WhatsApp Cloud API outbound adapter.

Posts a text message to the Graph API with a bounded retry and exponential
backoff. ``httpx`` is imported lazily inside :meth:`WhatsAppOutbound.send` so
the module never forces the dependency at import time.
"""

from __future__ import annotations

import asyncio
import logging

from revenueflow.config import get_settings
from revenueflow.domain.errors import ChannelError

_LOGGER = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
_TIMEOUT_SECONDS = 10.0


class WhatsAppOutbound:
    """``ChannelOutbound`` that delivers replies through the WhatsApp Graph API."""

    async def send(self, *, phone: str, text: str, dispatch_key: str) -> None:
        import httpx

        settings = get_settings()
        url = f"{_GRAPH_API_BASE}/{settings.whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "X-RF-Dispatch-Key": dispatch_key,
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }

        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                    response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                last_error = exc
                _LOGGER.warning(
                    "whatsapp outbound attempt %d/%d failed",
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    exc_info=True,
                )
            if attempt + 1 < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_SECONDS[attempt])

        raise ChannelError("whatsapp outbound send failed") from last_error
