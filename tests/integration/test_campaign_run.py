from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.domain.models import (
    Customer,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import fetchone, unit_of_work
from revenueflow.services.campaign import run


class _RaisingOutbound:
    async def send(self, *, phone: str, text: str, dispatch_key: str) -> None:
        raise RuntimeError("whatsapp send failed")


@pytest.fixture
def outbound() -> Iterator[FakeOutbound]:
    fake = FakeOutbound()
    token = set_outbound(fake)
    try:
        yield fake
    finally:
        reset_outbound(token)


async def _customer(*, opted_in: bool) -> Customer:
    customer_id = f"CUST-CAMP-{uuid4().hex[:8]}"
    phone = f"+5511{uuid4().hex[:9]}"
    async with unit_of_work() as conn:
        await customer_repo.create(
            conn,
            Customer(
                customer_id=customer_id,
                phone=phone,
                name="Campaign Test",
                segment=None,
                created_at=datetime.now(UTC),
            ),
        )
        if opted_in:
            await customer_repo.set_consent_opt_in(conn, customer_id, datetime.now(UTC))
        stored = await customer_repo.get_by_id(conn, customer_id)
    assert stored is not None
    return stored


async def _opportunity(customer_id: str) -> Opportunity:
    opp = Opportunity(
        opportunity_id=uuid4().hex,
        customer_id=customer_id,
        opportunity_type=OpportunityType.REPLENISHMENT,
        product="PMP-100-CEN",
        estimated_revenue=Decimal("500.00"),
        probability=Decimal("0.35"),
        reason="teste",
        evidence={"threshold": 1.5},
        recommended_action="offer_replenishment",
        status=OpportunityStatus.OPEN,
        created_at=datetime.now(UTC),
    )
    async with unit_of_work() as conn:
        await opportunity_repo.upsert_open(conn, opp)
    return opp


async def _contact_row(customer_id: str, opportunity_id: str) -> dict[str, Any] | None:
    async with unit_of_work() as conn:
        return await fetchone(
            conn,
            "SELECT status, skip_reason FROM outbound_contact "
            "WHERE customer_id = %s AND opportunity_id = %s "
            "ORDER BY contacted_at DESC LIMIT 1",
            (customer_id, opportunity_id),
        )


async def test_run_sends_to_opted_in_customer(db: None, outbound: FakeOutbound) -> None:
    customer = await _customer(opted_in=True)
    opp = await _opportunity(customer.customer_id)

    result = await run(now=datetime.now(UTC))

    assert result.sent >= 1
    assert any(entry["phone"] == customer.phone for entry in outbound.sent)

    row = await _contact_row(customer.customer_id, opp.opportunity_id)
    assert row is not None
    assert row["status"] == "SENT"


async def test_run_skips_customer_without_consent(db: None, outbound: FakeOutbound) -> None:
    customer = await _customer(opted_in=False)
    opp = await _opportunity(customer.customer_id)

    result = await run(now=datetime.now(UTC))

    assert result.skipped >= 1
    assert all(entry["phone"] != customer.phone for entry in outbound.sent)

    row = await _contact_row(customer.customer_id, opp.opportunity_id)
    assert row is not None
    assert row["status"] == "SKIPPED"
    assert row["skip_reason"] == "no_consent"


async def test_run_counts_error_for_missing_customer(db: None, outbound: FakeOutbound) -> None:
    missing_customer_id = f"CUST-GHOST-{uuid4().hex[:8]}"
    await _opportunity(missing_customer_id)

    result = await run(now=datetime.now(UTC))

    assert result.errors >= 1


async def test_run_records_failed_on_send_error(db: None) -> None:
    raising = _RaisingOutbound()
    token = set_outbound(raising)  # type: ignore[arg-type]
    try:
        customer = await _customer(opted_in=True)
        opp = await _opportunity(customer.customer_id)

        result = await run(now=datetime.now(UTC))
    finally:
        reset_outbound(token)

    assert result.failed >= 1
    row = await _contact_row(customer.customer_id, opp.opportunity_id)
    assert row is not None
    assert row["status"] == "FAILED"


async def test_run_twice_same_day_does_not_resend(db: None, outbound: FakeOutbound) -> None:
    customer = await _customer(opted_in=True)
    await _opportunity(customer.customer_id)
    moment = datetime.now(UTC)

    first = await run(now=moment)
    sent_after_first = len(outbound.sent)
    assert first.sent >= 1

    await run(now=moment)

    assert len(outbound.sent) == sent_after_first


def test_campaign_service_imports_no_graph_or_llm() -> None:
    source = Path("src/revenueflow/services/campaign.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.services.llm" not in import_lines


def test_campaign_job_has_no_scheduler() -> None:
    tf = Path("infra/terraform/campaign_job.tf").read_text(encoding="utf-8")
    assert "google_cloud_run_v2_job" in tf
    assert "google_cloud_scheduler_job" not in tf
