"""Internal approval decision routes (SPEC-012, ADR-050).

``GET /internal/approvals?status=PENDING`` lists the open approvals; ``POST
/internal/approvals/{approval_id}`` records an operator's decision. Both require
a bearer token (``APPROVAL_API_TOKEN``); the decision route publishes the event
that resumes the paused turn. The service is public (``allUsers`` invoker) so
the bearer check is the only gate, mirroring the webhook HMAC.
"""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel, model_validator

from revenueflow.config import get_settings
from revenueflow.domain.errors import DomainError
from revenueflow.services import approval as approval_svc

router = APIRouter(prefix="/internal/approvals", tags=["approvals"])


def _auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().approval_api_token
    if token == "":
        raise HTTPException(status_code=503, detail="approval api not configured")
    if authorization is None or not secrets.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


class Decision(BaseModel):
    decision: Literal["approve", "approve_with_override", "reject"]
    discount_pct: Decimal | None = None

    @model_validator(mode="after")
    def _override_needs_pct(self) -> Decision:
        if (self.decision == "approve_with_override") != (self.discount_pct is not None):
            raise ValueError("discount_pct is required iff decision is approve_with_override")
        return self


@router.get("", dependencies=[Depends(_auth)])
async def list_pending(status: Annotated[str, Query()] = "PENDING") -> list[dict[str, Any]]:
    if status != "PENDING":
        raise HTTPException(status_code=422, detail="only status=PENDING is supported")
    return await approval_svc.list_pending()


@router.post("/{approval_id}", dependencies=[Depends(_auth)])
async def decide(
    approval_id: Annotated[str, Path()],
    body: Decision,
) -> dict[str, Any]:
    try:
        return await approval_svc.decide(approval_id, body.decision, body.discount_pct)
    except DomainError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
