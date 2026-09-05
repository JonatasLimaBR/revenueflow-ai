import sys
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from revenueflow.repositories import analytics as analytics_repo
from revenueflow.services import analytics_sync

_CONV_ROW = {
    "conversation_id": "c1",
    "ai_cost_usd": 1.5,
    "turns": 2,
    "last_at": "2026-09-04T00:00:00",
    "orders": 1,
    "revenue": 100.0,
    "margin_usd": 40.0,
    "recovered_revenue_usd": 0.0,
}

_OUTCOME_ROW = {"outcome": "replied", "turns": 5, "cost_usd": 2.0, "avg_latency_ms": 300.0}

_CUSTOMER_360_ROW = {
    "customer_id": "cust1",
    "orders_12m": 3,
    "revenue_12m": 300.0,
    "last_purchase": "2026-09-01T00:00:00",
    "purchase_interval_days": 10.0,
    "preferred_product": "p1",
    "open_quotes": 1,
}

_LEAD_FUNNEL_ROW = {"lead_id": "lead1", "status": "QUALIFIED", "created_at": "2026-08-01T00:00:00"}

_OPPORTUNITY_SUMMARY_ROW = {
    "opportunity_id": "opp1",
    "customer_id": "cust1",
    "opportunity_type": "REPLENISHMENT",
    "status": "OPEN",
    "estimated_revenue": 50.0,
    "probability": 0.4,
    "created_at": "2026-08-15T00:00:00",
}

_HANDOFF_RATE_ROW = {"total_turns": 10, "handoff_turns": 2}

_ALL_TABLES = {
    "conversation_revenue",
    "cost_per_outcome",
    "customer_360",
    "lead_funnel",
    "opportunity_summary",
    "handoff_rate",
}


@asynccontextmanager
async def _fake_read_connection() -> AsyncIterator[None]:
    yield None


@pytest.fixture
def bq(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"fail_tables": set(), "calls": []}

    class _FakeLoadJob:
        def __init__(self, should_fail: bool) -> None:
            self._should_fail = should_fail

        def result(self) -> None:
            if self._should_fail:
                raise RuntimeError("load failed")

    class _FakeClient:
        project = "test-project"

        def load_table_from_json(
            self, rows: list[dict[str, Any]], table_ref: str, job_config: Any = None
        ) -> _FakeLoadJob:
            state["calls"].append((rows, table_ref, job_config))
            table = table_ref.rsplit(".", 1)[-1]
            return _FakeLoadJob(should_fail=table in state["fail_tables"])

    class _FakeWriteDisposition:
        WRITE_TRUNCATE = "WRITE_TRUNCATE"

    class _FakeSchemaField:
        def __init__(self, name: str, field_type: str) -> None:
            self.name = name
            self.field_type = field_type

    class _FakeLoadJobConfig:
        def __init__(self, write_disposition: Any = None, schema: Any = None) -> None:
            self.write_disposition = write_disposition
            self.schema = schema

    fake_module = types.ModuleType("google.cloud.bigquery")
    fake_module.Client = _FakeClient  # type: ignore[attr-defined]
    fake_module.LoadJobConfig = _FakeLoadJobConfig  # type: ignore[attr-defined]
    fake_module.WriteDisposition = _FakeWriteDisposition  # type: ignore[attr-defined]
    fake_module.SchemaField = _FakeSchemaField  # type: ignore[attr-defined]

    google_mod = sys.modules.get("google")
    if google_mod is None:
        google_mod = types.ModuleType("google")
        monkeypatch.setitem(sys.modules, "google", google_mod)

    cloud_mod = sys.modules.get("google.cloud")
    if cloud_mod is None:
        cloud_mod = types.ModuleType("google.cloud")
        monkeypatch.setitem(sys.modules, "google.cloud", cloud_mod)
    monkeypatch.setattr(google_mod, "cloud", cloud_mod, raising=False)

    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", fake_module)
    monkeypatch.setattr(cloud_mod, "bigquery", fake_module, raising=False)
    return state


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics_sync, "read_connection", _fake_read_connection)

    async def _conv(conn: object) -> list[dict[str, Any]]:
        return [dict(_CONV_ROW)]

    async def _outcome(conn: object) -> list[dict[str, Any]]:
        return [dict(_OUTCOME_ROW)]

    async def _customer_360(conn: object) -> list[dict[str, Any]]:
        return [dict(_CUSTOMER_360_ROW)]

    async def _lead_funnel(conn: object) -> list[dict[str, Any]]:
        return [dict(_LEAD_FUNNEL_ROW)]

    async def _opportunity_summary(conn: object) -> list[dict[str, Any]]:
        return [dict(_OPPORTUNITY_SUMMARY_ROW)]

    async def _handoff_rate(conn: object) -> list[dict[str, Any]]:
        return [dict(_HANDOFF_RATE_ROW)]

    monkeypatch.setattr(analytics_repo, "conversation_revenue", _conv)
    monkeypatch.setattr(analytics_repo, "cost_per_outcome", _outcome)
    monkeypatch.setattr(analytics_repo, "customer_360_all", _customer_360)
    monkeypatch.setattr(analytics_repo, "lead_funnel", _lead_funnel)
    monkeypatch.setattr(analytics_repo, "opportunity_summary", _opportunity_summary)
    monkeypatch.setattr(analytics_repo, "handoff_rate", _handoff_rate)


async def test_run_loads_all_six_tables(bq: dict[str, Any]) -> None:
    result = await analytics_sync.run()

    assert result.errors == 0
    assert set(result.rows_loaded) == _ALL_TABLES
    assert all(count == 1 for count in result.rows_loaded.values())
    assert len(bq["calls"]) == 6
    tables = {call[1].rsplit(".", 1)[-1] for call in bq["calls"]}
    assert tables == _ALL_TABLES


async def test_run_uses_write_truncate_for_all_loads(bq: dict[str, Any]) -> None:
    await analytics_sync.run()

    assert len(bq["calls"]) == 6
    for _, _, job_config in bq["calls"]:
        assert job_config.write_disposition == "WRITE_TRUNCATE"


async def test_run_survives_one_table_failing(bq: dict[str, Any]) -> None:
    bq["fail_tables"] = {"cost_per_outcome"}

    result = await analytics_sync.run()

    assert result.errors == 1
    assert "cost_per_outcome" not in result.rows_loaded
    assert set(result.rows_loaded) == _ALL_TABLES - {"cost_per_outcome"}


def test_analytics_tf_tables_have_no_pii_columns() -> None:
    tf = Path("infra/terraform/analytics.tf").read_text(encoding="utf-8")
    for field in ("phone", "name", "email", "cpf", "reason", "evidence"):
        assert f'"{field}"' not in tf


def test_analytics_tf_iam_is_dataset_scoped() -> None:
    tf = Path("infra/terraform/analytics.tf").read_text(encoding="utf-8")
    assert "google_bigquery_dataset_iam_member" in tf
    assert "google_project_iam_member" not in tf


def test_analytics_service_imports_no_graph_or_llm() -> None:
    source = Path("src/revenueflow/services/analytics_sync.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.services.llm" not in import_lines
