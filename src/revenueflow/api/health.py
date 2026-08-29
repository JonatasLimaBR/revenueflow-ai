"""Liveness and readiness probe (SPEC-034).

``GET /healthz`` runs a trivial query through the shared connection pool so the
probe fails closed (``503``) when the database is unreachable.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from revenueflow.repositories.db import execute, read_connection

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> Response:
    """Return ``200`` with ``db: true`` when the database answers, else ``503``."""

    try:
        async with read_connection() as conn:
            await execute(conn, "SELECT 1")
    except Exception:
        return JSONResponse({"status": "degraded", "db": False}, status_code=503)
    return JSONResponse({"status": "ok", "db": True})
