"""FastAPI application wiring (DESIGN §1.1 / §1.3).

The lifespan opens the shared connection pool, sets up the LangGraph Postgres
checkpointer, compiles the turn graph, and registers it with the worker so the
consumer and the webhook share one graph instance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from revenueflow.agents import build_graph
from revenueflow.api import health_router, webhook_router
from revenueflow.config import get_settings
from revenueflow.repositories.db import close_pool, open_pool
from revenueflow.worker import set_graph


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the pool and checkpointer for the life of the application."""

    await open_pool()
    async with AsyncPostgresSaver.from_conn_string(get_settings().database_url) as saver:
        await saver.setup()
        set_graph(build_graph(saver))
        yield
    await close_pool()


app = FastAPI(title="RevenueFlow AI", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(health_router)
