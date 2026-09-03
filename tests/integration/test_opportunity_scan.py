from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from revenueflow.domain.models import OpportunityStatus, OpportunityType
from revenueflow.policies import opportunity_policy
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import execute, unit_of_work
from revenueflow.services.opportunity import scan

_SEED_ORDER = """
INSERT INTO sim_customer_order (customer_id, order_id, total, ordered_at, items)
VALUES (%s, %s, %s, now() - (%s || ' days')::interval, '[]'::jsonb)
"""

_SEED_QUOTE = """
INSERT INTO quote (
    quote_id, conversation_id, customer_ref, items, total, expiration, status, created_at
)
VALUES (
    %s, %s, %s, %s::jsonb, %s, now() + interval '7 days', 'SENT', now() - interval '5 days'
)
"""


async def _overdue_customer() -> str:
    customer_id = f"CUST-OVD-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await execute(conn, _SEED_ORDER, (customer_id, uuid4().hex, "800.00", 200))
        await execute(conn, _SEED_ORDER, (customer_id, uuid4().hex, "800.00", 150))
    return customer_id


async def _stale_quote() -> tuple[str, str]:
    quote_id = uuid4().hex
    customer_ref = f"CUST-QR-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await execute(
            conn,
            _SEED_QUOTE,
            (quote_id, uuid4().hex, customer_ref, '[{"product_id": "PMP-100-CEN"}]', "999.00"),
        )
    return quote_id, customer_ref


async def test_scan_detects_replenishment_and_quote_recovery(db: None) -> None:
    overdue = await _overdue_customer()
    quote_id, quote_customer = await _stale_quote()

    result = await scan(now=datetime.now(UTC))

    assert result.replenishment >= 1
    assert result.quote_recovery >= 1
    assert result.created >= 2
    assert result.errors == 0

    async with unit_of_work() as conn:
        opens = await opportunity_repo.list_by_status(conn, OpportunityStatus.OPEN)

    rep = next(o for o in opens if o.customer_id == overdue)
    assert rep.opportunity_type is OpportunityType.REPLENISHMENT
    assert rep.reason
    assert rep.evidence["threshold"] == 1.5

    rec = next(o for o in opens if o.customer_id == quote_customer)
    assert rec.opportunity_type is OpportunityType.QUOTE_RECOVERY
    assert rec.evidence["quote_id"] == quote_id


async def test_rescan_creates_nothing(db: None) -> None:
    await _overdue_customer()
    await _stale_quote()

    first = await scan(now=datetime.now(UTC))
    assert first.created >= 2

    second = await scan(now=datetime.now(UTC))
    assert second.created == 0


async def test_scan_survives_a_failing_candidate(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    await _overdue_customer()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("rule blew up")

    monkeypatch.setattr(opportunity_policy, "replenishment", _boom)

    result = await scan(now=datetime.now(UTC))

    assert result.errors >= 1


def test_scan_service_imports_no_graph_or_channel() -> None:
    source = Path("src/revenueflow/services/opportunity.py").read_text(encoding="utf-8")
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    ]
    joined = "\n".join(import_lines)
    assert "revenueflow.agents" not in joined
    assert "revenueflow.adapters" not in joined
    assert "revenueflow.services.llm" not in joined


def test_opportunity_job_has_no_scheduler() -> None:
    tf = Path("infra/terraform/opportunity_job.tf").read_text(encoding="utf-8")
    assert "google_cloud_run_v2_job" in tf
    assert "google_cloud_scheduler_job" not in tf
