from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.domain.models import Intent, LeadStatus
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories.db import execute, unit_of_work
from revenueflow.services.lead_lifecycle import advance_from_turn

_INSERT_LEAD = "INSERT INTO lead (lead_id, phone, status, created_at) VALUES (%s, %s, %s, %s)"


async def _seed_lead(conn: object, *, status: LeadStatus = LeadStatus.NEW) -> tuple[str, str]:
    lead_id = uuid4().hex
    phone = f"+5511{uuid4().hex[:9]}"
    await execute(conn, _INSERT_LEAD, (lead_id, phone, status.value, datetime.now(UTC)))
    return lead_id, phone


async def test_advance_from_turn_updates_status(db: None) -> None:
    async with unit_of_work() as conn:
        lead_id, _ = await _seed_lead(conn)

    await advance_from_turn(lead_id=lead_id, intent=Intent.PRODUCT_SEARCH.value, final_outcome=None)

    async with unit_of_work() as conn:
        stored = await lead_repo.get_by_id(conn, lead_id)
    assert stored is not None
    assert stored.status is LeadStatus.QUALIFYING


async def test_advance_from_turn_promotes_to_customer_on_ordered(db: None) -> None:
    async with unit_of_work() as conn:
        lead_id, phone = await _seed_lead(conn, status=LeadStatus.PROPOSAL)

    await advance_from_turn(
        lead_id=lead_id, intent=Intent.ORDER_REQUEST.value, final_outcome="ordered"
    )

    async with unit_of_work() as conn:
        stored_lead = await lead_repo.get_by_id(conn, lead_id)
        stored_customer = await customer_repo.get_by_phone(conn, phone)
    assert stored_lead is not None
    assert stored_lead.status is LeadStatus.WON
    assert stored_customer is not None
    assert stored_customer.phone == phone


async def test_advance_from_turn_promotion_is_idempotent(db: None) -> None:
    async with unit_of_work() as conn:
        lead_id, phone = await _seed_lead(conn, status=LeadStatus.PROPOSAL)

    await advance_from_turn(
        lead_id=lead_id, intent=Intent.ORDER_REQUEST.value, final_outcome="ordered"
    )
    await advance_from_turn(
        lead_id=lead_id, intent=Intent.ORDER_REQUEST.value, final_outcome="ordered"
    )

    async with unit_of_work() as conn:
        rows = await customer_repo.get_by_phone(conn, phone)
    assert rows is not None


async def test_advance_from_turn_noop_without_lead_id(db: None) -> None:
    await advance_from_turn(
        lead_id=None, intent=Intent.ORDER_REQUEST.value, final_outcome="ordered"
    )
