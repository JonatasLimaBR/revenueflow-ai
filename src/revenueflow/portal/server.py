"""Operational portal FastAPI app (ADR-073). Own Cloud Run service, own
lifespan (opens the shared pool — same DATABASE_URL as the API, no new
connection path). Security headers mirror main.py's middleware."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse

from revenueflow.observability.logging_setup import configure_logging
from revenueflow.portal.views import router as portal_router
from revenueflow.repositories.db import close_pool, open_pool

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await open_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(title="RevenueFlow Portal", lifespan=lifespan)


@app.middleware("http")
async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


app.include_router(portal_router)


@app.get("/")
async def _root() -> RedirectResponse:
    return RedirectResponse(url="/portal/")


@app.get("/healthz")
async def _healthz() -> dict[str, str]:
    return {"status": "ok"}
