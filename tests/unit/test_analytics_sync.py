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
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", fake_module)
    return state


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics_sync, "read_connection", _fake_read_connection)

    async def _conv(conn: object) -> list[dict[str, Any]]:
        return [dict(_CONV_ROW)]

    async def _outcome(conn: object) -> list[dict[str, Any]]:
        return [dict(_OUTCOME_ROW)]

    monkeypatch.setattr(analytics_repo, "conversation_revenue", _conv)
    monkeypatch.setattr(analytics_repo, "cost_per_outcome", _outcome)


async def test_run_loads_both_tables(bq: dict[str, Any]) -> None:
    result = await analytics_sync.run()

    assert result.conversation_rows == 1
    assert result.outcome_rows == 1
    assert result.errors == 0
    assert len(bq["calls"]) == 2
    tables = {call[1].rsplit(".", 1)[-1] for call in bq["calls"]}
    assert tables == {"conversation_revenue", "cost_per_outcome"}


async def test_run_uses_write_truncate_for_both_loads(bq: dict[str, Any]) -> None:
    await analytics_sync.run()

    assert len(bq["calls"]) == 2
    for _, _, job_config in bq["calls"]:
        assert job_config.write_disposition == "WRITE_TRUNCATE"


async def test_run_survives_one_table_failing(bq: dict[str, Any]) -> None:
    bq["fail_tables"] = {"cost_per_outcome"}

    result = await analytics_sync.run()

    assert result.conversation_rows == 1
    assert result.outcome_rows == 0
    assert result.errors == 1


def test_analytics_tf_tables_have_no_pii_columns() -> None:
    tf = Path("infra/terraform/analytics.tf").read_text(encoding="utf-8")
    for field in ("phone", "name", "email", "cpf"):
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
