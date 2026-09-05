from datetime import UTC, datetime, timedelta
from uuid import uuid4

from revenueflow.domain.models import ConversationSession, LeadStatus, SessionStatus
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import execute, unit_of_work

_INSERT_LEAD = "INSERT INTO lead (lead_id, phone, status, created_at) VALUES (%s, %s, %s, %s)"


async def _seed_lead(conn: object, *, status: LeadStatus, created_at: datetime) -> tuple[str, str]:
    lead_id = uuid4().hex
    phone = f"+5511{uuid4().hex[:9]}"
    await execute(conn, _INSERT_LEAD, (lead_id, phone, status.value, created_at))
    return lead_id, phone


async def test_get_by_id_and_set_status(db: None) -> None:
    async with unit_of_work() as conn:
        lead_id, _ = await _seed_lead(conn, status=LeadStatus.NEW, created_at=datetime.now(UTC))
        await lead_repo.set_status(conn, lead_id, LeadStatus.QUALIFYING)
        stored = await lead_repo.get_by_id(conn, lead_id)

    assert stored is not None
    assert stored.status is LeadStatus.QUALIFYING


async def test_stale_candidates_uses_created_at_without_session(db: None) -> None:
    async with unit_of_work() as conn:
        old_id, _ = await _seed_lead(
            conn, status=LeadStatus.NEW, created_at=datetime.now(UTC) - timedelta(days=40)
        )
        fresh_id, _ = await _seed_lead(
            conn, status=LeadStatus.NEW, created_at=datetime.now(UTC) - timedelta(days=1)
        )
        stale = await lead_repo.stale_candidates(conn, stale_after_days=30)

    stale_ids = {lead.lead_id for lead in stale}
    assert old_id in stale_ids
    assert fresh_id not in stale_ids


async def test_stale_candidates_uses_recent_session_activity(db: None) -> None:
    async with unit_of_work() as conn:
        lead_id, phone = await _seed_lead(
            conn, status=LeadStatus.QUALIFYING, created_at=datetime.now(UTC) - timedelta(days=90)
        )
        await session_repo.create(
            conn,
            ConversationSession(
                conversation_id=uuid4().hex,
                phone=phone,
                status=SessionStatus.OPEN,
                last_interaction=datetime.now(UTC) - timedelta(days=2),
            ),
        )
        stale = await lead_repo.stale_candidates(conn, stale_after_days=30)

    assert lead_id not in {lead.lead_id for lead in stale}


async def test_stale_candidates_excludes_terminal_statuses(db: None) -> None:
    async with unit_of_work() as conn:
        won_id, _ = await _seed_lead(
            conn, status=LeadStatus.WON, created_at=datetime.now(UTC) - timedelta(days=90)
        )
        lost_id, _ = await _seed_lead(
            conn, status=LeadStatus.LOST, created_at=datetime.now(UTC) - timedelta(days=90)
        )
        stale = await lead_repo.stale_candidates(conn, stale_after_days=30)

    stale_ids = {lead.lead_id for lead in stale}
    assert won_id not in stale_ids
    assert lost_id not in stale_ids
