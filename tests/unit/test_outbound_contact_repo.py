from uuid import uuid4

from revenueflow.domain.models import CampaignContactStatus, CampaignSkipReason
from revenueflow.repositories import outbound_contact as contact_repo
from revenueflow.repositories.db import fetchall, unit_of_work


async def test_last_contact_at_only_counts_sent(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"
    opp_id = uuid4().hex

    async with unit_of_work() as conn:
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=opp_id,
            status=CampaignContactStatus.SENT,
        )
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=opp_id,
            status=CampaignContactStatus.SKIPPED,
            skip_reason=CampaignSkipReason.FREQUENCY_CAPPED,
        )
        last = await contact_repo.last_contact_at(conn, customer_id)

    assert last is not None


async def test_last_contact_at_none_when_never_sent(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"

    async with unit_of_work() as conn:
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=uuid4().hex,
            status=CampaignContactStatus.SKIPPED,
            skip_reason=CampaignSkipReason.NO_CONSENT,
        )
        last = await contact_repo.last_contact_at(conn, customer_id)

    assert last is None


async def test_record_persists_all_statuses(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"

    async with unit_of_work() as conn:
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=uuid4().hex,
            status=CampaignContactStatus.SENT,
        )
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=uuid4().hex,
            status=CampaignContactStatus.SKIPPED,
            skip_reason=CampaignSkipReason.OPTED_OUT,
        )
        await contact_repo.record(
            conn,
            customer_id=customer_id,
            opportunity_id=uuid4().hex,
            status=CampaignContactStatus.FAILED,
        )
        rows = await fetchall(
            conn,
            "SELECT status, skip_reason FROM outbound_contact WHERE customer_id = %s",
            (customer_id,),
        )

    statuses = {row["status"] for row in rows}
    assert statuses == {"SENT", "SKIPPED", "FAILED"}
    skipped = next(row for row in rows if row["status"] == "SKIPPED")
    assert skipped["skip_reason"] == "opted_out"
