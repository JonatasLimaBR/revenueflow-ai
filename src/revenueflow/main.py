"""FastAPI application wiring (DESIGN §1.1 / §1.3).

The lifespan opens the shared connection pool, sets up the LangGraph Postgres
checkpointer, compiles the turn graph, and registers it with the worker so the
consumer and the webhook share one graph instance.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from revenueflow.agents import build_graph
from revenueflow.api import (
    approvals_router,
    audit_router,
    handoffs_router,
    health_router,
    webhook_router,
)
from revenueflow.config import get_settings
from revenueflow.observability.logging_setup import configure_logging
from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.worker import set_graph
from revenueflow.worker.subscriber import run_subscriber


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the pool and checkpointer for the life of the application."""

    configure_logging()
    settings = get_settings()
    if settings.tracer_sink == "otel":
        from revenueflow.observability.otel_setup import configure_otel

        configure_otel()
    await open_pool()
    # AsyncPostgresSaver.from_conn_string holds ONE bare connection for the
    # whole app lifetime, shared (behind the saver's own asyncio.Lock) by
    # every concurrent turn's checkpoint I/O — found live: intermittent
    # multi-minute turn stalls (up to ~5m) that neither the retry-fixed
    # Vertex client (PR #82) nor the app's own pool (PR #83) explained,
    # because this connection is a separate, still-unpooled path. The saver
    # accepts an AsyncConnectionPool directly (checked via isinstance in its
    # own __init__) — a stuck/broken connection then just gets replaced by
    # the pool instead of wedging every future turn until instance restart.
    checkpoint_pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = AsyncConnectionPool(
        settings.database_url,
        open=False,
        min_size=2,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await checkpoint_pool.open()
    try:
        saver = AsyncPostgresSaver(checkpoint_pool)
        await saver.setup()
        set_graph(build_graph(saver))
        consumer: asyncio.Task[None] | None = None
        if get_settings().run_consumer:
            consumer = asyncio.create_task(run_subscriber(), name="pubsub-consumer")
        try:
            yield
        finally:
            if consumer is not None:
                consumer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await consumer
    finally:
        await checkpoint_pool.close()
    await close_pool()


app = FastAPI(title="RevenueFlow AI", lifespan=lifespan)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@app.middleware("http")
async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


app.include_router(webhook_router)
app.include_router(health_router)
app.include_router(approvals_router)
app.include_router(handoffs_router)
app.include_router(audit_router)
