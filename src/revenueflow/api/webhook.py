"""FastAPI routes for the WhatsApp Cloud API webhook (SPEC-001).

``GET /webhook/whatsapp`` answers the Meta verification handshake; ``POST
/webhook/whatsapp`` verifies the ``X-Hub-Signature-256`` HMAC, parses the body
into normalized events, and hands each one to :func:`ingest_message`. The route
returns fast (``202``) and leaves the turn work to the consumer.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from revenueflow.adapters import parse_inbound, verify_signature
from revenueflow.config import get_settings
from revenueflow.domain.errors import ChannelError
from revenueflow.services import ingest_message

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/whatsapp")
async def verify(
    hub_mode: Annotated[str, Query(alias="hub.mode")] = "",
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")] = "",
    hub_challenge: Annotated[str, Query(alias="hub.challenge")] = "",
) -> Response:
    """Echo ``hub.challenge`` when the verify token matches, else ``403``."""

    expected = get_settings().whatsapp_verify_token
    if hub_mode == "subscribe" and expected != "" and hub_verify_token == expected:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/whatsapp", status_code=202)
async def receive(request: Request) -> Response:
    """Verify the signature, normalize the body, and ingest each message."""

    raw = await request.body()
    if not verify_signature(
        raw,
        request.headers.get("X-Hub-Signature-256", ""),
        get_settings().whatsapp_app_secret,
    ):
        return Response(status_code=403)
    try:
        events = parse_inbound(raw)
    except ChannelError:
        return Response(status_code=400)
    for event in events:
        await ingest_message(event)
    return JSONResponse({"status": "accepted"}, status_code=202)
