"""Internal human-handoff routes (SPEC-026/027, ADR-054).

``GET /internal/handoffs?status=PENDING`` lists the open handoffs for a human
agent to pick up; ``POST /internal/handoffs/{handoff_id}`` marks one resolved.
Both require a bearer token (``HANDOFF_API_TOKEN``); the service is public
(``allUsers`` invoker) so the bearer check is the only gate, mirroring the
webhook HMAC and the approval route.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query

from revenueflow.config import get_settings
from revenueflow.services import handoff as handoff_svc

router = APIRouter(prefix="/internal/handoffs", tags=["handoffs"])


def _auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().handoff_api_token
    if token == "":
        raise HTTPException(status_code=503, detail="handoff api not configured")
    if authorization is None or not secrets.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("", dependencies=[Depends(_auth)])
async def list_pending(status: Annotated[str, Query()] = "PENDING") -> list[dict[str, Any]]:
    if status != "PENDING":
        raise HTTPException(status_code=422, detail="only status=PENDING is supported")
    return await handoff_svc.list_pending()


@router.post("/{handoff_id}", dependencies=[Depends(_auth)])
async def resolve(handoff_id: Annotated[str, Path()]) -> dict[str, str]:
    moved = await handoff_svc.resolve(handoff_id)
    return {"status": "resolved" if moved else "noop"}
