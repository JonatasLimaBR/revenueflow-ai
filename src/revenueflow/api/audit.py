"""Internal audit-reconstruction route (SPEC-028, PRD-013, ADR-055).

``GET /internal/audit/{conversation_id}`` returns the audited turns of a
conversation in time order, each with its full ``events`` list, so an operator
can reconstruct an attendance without reading the whole trace. Bearer-gated,
reusing ``HANDOFF_API_TOKEN`` (both are ops read-only scopes).
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path

from revenueflow.config import get_settings
from revenueflow.services import audit as audit_svc

router = APIRouter(prefix="/internal/audit", tags=["audit"])


def _auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().handoff_api_token
    if token == "":
        raise HTTPException(status_code=503, detail="audit api not configured")
    if authorization is None or not secrets.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/{conversation_id}", dependencies=[Depends(_auth)])
async def reconstruct(conversation_id: Annotated[str, Path()]) -> list[dict[str, Any]]:
    return await audit_svc.reconstruct(conversation_id)
