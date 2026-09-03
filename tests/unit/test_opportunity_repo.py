from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from revenueflow.domain.models import Opportunity, OpportunityStatus, OpportunityType
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import unit_of_work


def _opp(customer_id: str) -> Opportunity:
    return Opportunity(
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


async def test_upsert_open_is_idempotent_per_signal(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"
    first = _opp(customer_id)
    second = _opp(customer_id)

    async with unit_of_work() as conn:
        stored_first = await opportunity_repo.upsert_open(conn, first)
        stored_second = await opportunity_repo.upsert_open(conn, second)
        rows = await opportunity_repo.list_by_status(conn, OpportunityStatus.OPEN)

    assert stored_first.opportunity_id == first.opportunity_id
    assert stored_second.opportunity_id == first.opportunity_id
    assert len([r for r in rows if r.customer_id == customer_id]) == 1


async def test_set_status_removes_from_open_list(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"
    opp = _opp(customer_id)

    async with unit_of_work() as conn:
        await opportunity_repo.upsert_open(conn, opp)
        await opportunity_repo.set_status(conn, opp.opportunity_id, OpportunityStatus.CONVERTED)
        open_rows = await opportunity_repo.list_by_status(conn, OpportunityStatus.OPEN)
        converted_rows = await opportunity_repo.list_by_status(conn, OpportunityStatus.CONVERTED)

    assert all(r.customer_id != customer_id for r in open_rows)
    assert any(r.opportunity_id == opp.opportunity_id for r in converted_rows)
