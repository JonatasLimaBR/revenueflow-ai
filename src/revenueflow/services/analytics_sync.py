"""Revenue/cost/customer/lead/opportunity/handoff analytics sync (PRD-015, ADR-005/061/063).

``run`` is a batch job, outside the graph and outside ``process_event``, same
shape as ``services.opportunity.scan`` and ``services.campaign.run``: it reads
the already-computed OLTP views (Postgres stays the source of truth for the
business logic, ADR-004) and loads a full snapshot into BigQuery with
``WRITE_TRUNCATE`` — idempotent by construction, no dedup needed. A failure
loading one table does not block the others.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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

_CUSTOMER_360_SCHEMA = [
    ("customer_id", "STRING"),
    ("orders_12m", "INT64"),
    ("revenue_12m", "FLOAT64"),
    ("last_purchase", "TIMESTAMP"),
    ("purchase_interval_days", "FLOAT64"),
    ("preferred_product", "STRING"),
    ("open_quotes", "INT64"),
]

_LEAD_FUNNEL_SCHEMA = [
    ("lead_id", "STRING"),
    ("status", "STRING"),
    ("created_at", "TIMESTAMP"),
]

_OPPORTUNITY_SUMMARY_SCHEMA = [
    ("opportunity_id", "STRING"),
    ("customer_id", "STRING"),
    ("opportunity_type", "STRING"),
    ("status", "STRING"),
    ("estimated_revenue", "FLOAT64"),
    ("probability", "FLOAT64"),
    ("created_at", "TIMESTAMP"),
]

_HANDOFF_RATE_SCHEMA = [
    ("total_turns", "INT64"),
    ("handoff_turns", "INT64"),
]

# (BigQuery table name, repositories.analytics function name, BigQuery schema). The function is
# looked up by name on every call (``getattr(analytics_repo, fn_name)``) rather than bound once at
# import time, so tests can monkeypatch ``analytics_repo.<fn_name>`` and have it take effect here.
_SOURCES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("conversation_revenue", "conversation_revenue", _CONVERSATION_REVENUE_SCHEMA),
    ("cost_per_outcome", "cost_per_outcome", _COST_PER_OUTCOME_SCHEMA),
    ("customer_360", "customer_360_all", _CUSTOMER_360_SCHEMA),
    ("lead_funnel", "lead_funnel", _LEAD_FUNNEL_SCHEMA),
    ("opportunity_summary", "opportunity_summary", _OPPORTUNITY_SUMMARY_SCHEMA),
    ("handoff_rate", "handoff_rate", _HANDOFF_RATE_SCHEMA),
]


@dataclass(slots=True)
class SyncResult:
    rows_loaded: dict[str, int] = field(default_factory=dict)
    errors: int = 0


async def run() -> SyncResult:
    from google.cloud import bigquery

    settings = get_settings()
    result = SyncResult()
    trace_id = uuid4().hex[:8]
    client = bigquery.Client()

    async with read_connection() as conn:
        fetched = {
            name: await getattr(analytics_repo, fn_name)(conn) for name, fn_name, _ in _SOURCES
        }

    for name, _fn_name, schema in _SOURCES:
        rows = fetched[name]
        if _load(client, settings.bigquery_dataset, name, rows, schema, trace_id):
            result.rows_loaded[name] = len(rows)
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
