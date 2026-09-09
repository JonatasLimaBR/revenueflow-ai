from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from revenueflow.config import get_settings
from revenueflow.domain.models import (
    Approval,
    ApprovalStatus,
    HandoffReason,
    Quote,
    QuoteStatus,
    SessionStatus,
)
from revenueflow.events import InMemoryPublisher
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import get_or_create
from revenueflow.services.expiration import sweep
from revenueflow.services.handoff import resolve as resolve_handoff

_NOW = datetime.now(UTC)


async def _seed_approval(*, expires_at: datetime | None) -> tuple[str, str]:
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    approval = Approval(
        approval_id=uuid4().hex,
        conversation_id=session.conversation_id,
        turn_id=uuid4().hex,
        reason="discount_out_of_policy",
        requested_discount=Decimal("0.4"),
        current_margin=Decimal("0.2"),
        resulting_margin=Decimal("0.05"),
        amount=Decimal("1000"),
        customer_ref=None,
        status=ApprovalStatus.PENDING,
        expires_at=expires_at,
    )
    async with unit_of_work() as conn:
        await approval_repo.create_pending(conn, approval)
    return session.conversation_id, approval.approval_id


async def _seed_quote(*, expiration: datetime) -> tuple[str, str]:
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    quote = Quote(
        quote_id=uuid4().hex,
        conversation_id=session.conversation_id,
        customer_ref=None,
        items=[{"product_id": "PMP-100-CEN", "quantity": 1}],
        total=Decimal("100"),
        expiration=expiration,
        status=QuoteStatus.SENT,
    )
    async with unit_of_work() as conn:
        await checkout_repo.create_quote(conn, quote)
    return session.conversation_id, quote.quote_id


async def _seed_handoff(*, created_before: timedelta) -> tuple[str, str]:
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    async with unit_of_work() as conn:
        await session_repo.update_status(conn, session.conversation_id, SessionStatus.HUMAN_HANDOFF)
        handoff = await handoff_repo.create(
            conn, session.conversation_id, HandoffReason.EXPLICIT_REQUEST, {}
        )
        # created_at defaults to now() in the schema -- backdate it directly
        # so the sweep sees it as stale without waiting real time.
        await conn.execute(
            "UPDATE handoff SET created_at = %s WHERE handoff_id = %s",
            (_NOW - created_before, handoff.handoff_id),
        )
    return session.conversation_id, handoff.handoff_id


async def test_sweep_expires_stale_pending_approval_and_publishes_resume(
    db: None, publisher: InMemoryPublisher
) -> None:
    conversation_id, approval_id = await _seed_approval(expires_at=_NOW - timedelta(hours=1))

    result = await sweep(now=_NOW)

    assert result.approvals_expired == 1
    async with unit_of_work() as conn:
        stored = await approval_repo.get(conn, approval_id)
    assert stored is not None
    assert stored.status is ApprovalStatus.EXPIRED
    published = [e for _topic, e in publisher.published if e.event_type == "approval_decided"]
    assert any(e.payload["conversation_id"] == conversation_id for e in published)


async def test_sweep_leaves_approval_alone_before_expiry(db: None) -> None:
    _, approval_id = await _seed_approval(expires_at=_NOW + timedelta(hours=1))

    result = await sweep(now=_NOW)

    assert result.approvals_expired == 0
    async with unit_of_work() as conn:
        stored = await approval_repo.get(conn, approval_id)
    assert stored is not None
    assert stored.status is ApprovalStatus.PENDING


async def test_sweep_expires_stale_quote_and_it_stops_being_open(db: None) -> None:
    conversation_id, quote_id = await _seed_quote(expiration=_NOW - timedelta(hours=1))

    result = await sweep(now=_NOW)

    assert result.quotes_expired == 1
    async with unit_of_work() as conn:
        open_quote = await checkout_repo.get_open_quote(conn, conversation_id)
    assert open_quote is None


async def test_sweep_leaves_quote_alone_before_expiry(db: None) -> None:
    conversation_id, _ = await _seed_quote(expiration=_NOW + timedelta(hours=1))

    result = await sweep(now=_NOW)

    assert result.quotes_expired == 0
    async with unit_of_work() as conn:
        open_quote = await checkout_repo.get_open_quote(conn, conversation_id)
    assert open_quote is not None


async def test_sweep_resolves_stale_handoff_and_reopens_session(db: None) -> None:
    stale_hours = get_settings().handoff_stale_hours
    conversation_id, handoff_id = await _seed_handoff(
        created_before=timedelta(hours=stale_hours + 1)
    )

    result = await sweep(now=_NOW)

    assert result.handoffs_expired == 1
    async with unit_of_work() as conn:
        session = await session_repo.get_open_by_phone(
            conn, await session_repo.phone_for(conn, conversation_id)
        )
    assert session is not None
    assert session.status is SessionStatus.OPEN


async def test_sweep_leaves_recent_handoff_alone(db: None) -> None:
    conversation_id, _ = await _seed_handoff(created_before=timedelta(minutes=5))

    result = await sweep(now=_NOW)

    assert result.handoffs_expired == 0
    async with unit_of_work() as conn:
        session = await session_repo.get_open_by_phone(
            conn, await session_repo.phone_for(conn, conversation_id)
        )
    assert session is not None
    assert session.status is SessionStatus.HUMAN_HANDOFF


async def test_resolve_handoff_reopens_the_session(db: None) -> None:
    conversation_id, handoff_id = await _seed_handoff(created_before=timedelta(hours=1))

    resolved = await resolve_handoff(handoff_id)

    assert resolved is True
    async with unit_of_work() as conn:
        session = await session_repo.get_open_by_phone(
            conn, await session_repo.phone_for(conn, conversation_id)
        )
    assert session is not None
    assert session.status is SessionStatus.OPEN


async def test_resolve_handoff_is_idempotent(db: None) -> None:
    _, handoff_id = await _seed_handoff(created_before=timedelta(hours=1))

    assert await resolve_handoff(handoff_id) is True
    assert await resolve_handoff(handoff_id) is False
