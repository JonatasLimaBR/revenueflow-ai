from decimal import Decimal
from uuid import uuid4

from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work


def _make(conversation_id: str, turn_id: str) -> Approval:
    return Approval(
        approval_id=uuid4().hex,
        conversation_id=conversation_id,
        turn_id=turn_id,
        reason="discount_out_of_policy",
        requested_discount=Decimal("0.40"),
        current_margin=Decimal("0.3000"),
        resulting_margin=Decimal("0.0500"),
        amount=Decimal("1234.56"),
        customer_ref="CUST-001",
        status=ApprovalStatus.PENDING,
    )


async def test_create_pending_is_idempotent_per_turn(db: None) -> None:
    conversation_id = f"conv-{uuid4().hex}"
    turn_id = f"turn-{uuid4().hex}"

    async with unit_of_work() as conn:
        first = _make(conversation_id, turn_id)
        assert await approval_repo.create_pending(conn, first) is True
        assert await approval_repo.create_pending(conn, _make(conversation_id, turn_id)) is False

        stored = await approval_repo.get_by_turn(conn, conversation_id, turn_id)
        assert stored is not None
        assert stored.approval_id == first.approval_id
        assert stored.status is ApprovalStatus.PENDING
        assert stored.requested_discount == Decimal("0.40")
        assert stored.amount == Decimal("1234.56")
        assert stored.customer_ref == "CUST-001"

        other_turn = f"turn-{uuid4().hex}"
        assert await approval_repo.create_pending(conn, _make(conversation_id, other_turn)) is True


async def test_get_by_turn_returns_none_when_absent(db: None) -> None:
    conversation_id = f"conv-{uuid4().hex}"
    turn_id = f"turn-{uuid4().hex}"
    async with unit_of_work() as conn:
        assert await approval_repo.get_by_turn(conn, conversation_id, turn_id) is None
