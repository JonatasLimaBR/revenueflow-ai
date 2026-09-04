"""Revenue + AI-cost analytics sync (PRD-015, ADR-005/061).

``run`` is a batch job, outside the graph and outside ``process_event``, same
shape as ``services.opportunity.scan`` and ``services.campaign.run``: it reads
the already-computed OLTP views (Postgres stays the source of truth for the
business logic, ADR-004) and loads a full snapshot into BigQuery with
``WRITE_TRUNCATE`` — idempotent by construction, no dedup needed. A failure
loading one table does not block the other.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from revenueflow.config import get_settings
from revenueflow.repositories import analytics as analytics_repo
from revenueflow.repositories.db import read_connection

_LOGGER = logging.getLogger(__name__)

_CONVERSATION_REVENUE_SCHEMA = [
    ("conversation_id", "STRING"),
    ("ai_cost_usd", "FLOAT64"),
    ("turns", "INT64"),
    ("last_at", "TIMESTAMP"),
    ("orders", "INT64"),
    ("revenue", "FLOAT64"),
    ("margin_usd", "FLOAT64"),
    ("recovered_revenue_usd", "FLOAT64"),
]

_COST_PER_OUTCOME_SCHEMA = [
    ("outcome", "STRING"),
    ("turns", "INT64"),
    ("cost_usd", "FLOAT64"),
    ("avg_latency_ms", "FLOAT64"),
]


@dataclass(slots=True)
class SyncResult:
    conversation_rows: int = 0
    outcome_rows: int = 0
    errors: int = 0


async def run() -> SyncResult:
    from google.cloud import bigquery

    settings = get_settings()
    result = SyncResult()
    trace_id = uuid4().hex[:8]

    async with read_connection() as conn:
        conv_rows = await analytics_repo.conversation_revenue(conn)
        outcome_rows = await analytics_repo.cost_per_outcome(conn)

    client = bigquery.Client()

    if _load(
        client,
        settings.bigquery_dataset,
        "conversation_revenue",
        conv_rows,
        _CONVERSATION_REVENUE_SCHEMA,
        trace_id,
    ):
        result.conversation_rows = len(conv_rows)
    else:
        result.errors += 1

    if _load(
        client,
        settings.bigquery_dataset,
        "cost_per_outcome",
        outcome_rows,
        _COST_PER_OUTCOME_SCHEMA,
        trace_id,
    ):
        result.outcome_rows = len(outcome_rows)
    else:
        result.errors += 1

    return result


def _load(
    client: Any,
    dataset: str,
    table: str,
    rows: list[dict[str, Any]],
    schema: list[tuple[str, str]],
    trace_id: str,
) -> bool:
    from google.cloud import bigquery

    table_ref = f"{client.project}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[bigquery.SchemaField(name, type_) for name, type_ in schema],
    )
    try:
        client.load_table_from_json(rows, table_ref, job_config=job_config).result()
        return True
    except Exception:
        _LOGGER.exception("analytics sync failed for %s trace_id=%s", table, trace_id)
        return False
