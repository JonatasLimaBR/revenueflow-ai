from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from revenueflow.agents.apply_decision import apply_decision_node
from revenueflow.domain.models import Approval, ApprovalStatus
from revenueflow.repositories import approval as approval_repo
from revenueflow.repositories.db import unit_of_work

_QUOTE = {"customer_price": "1000.00", "unit_cost": "600.00", "valid_until": "2026-12-31"}


async def _seed(*, requested: str, expires_delta: timedelta) -> str:
    approval = Approval(
        approval_id=uuid4().hex,
        conversation_id=f"c-{uuid4().hex}",
        turn_id=f"t-{uuid4().hex}",
        reason="discount_out_of_policy",
        requested_discount=Decimal(requested),
        current_margin=Decimal("0.3000"),
        resulting_margin=Decimal("0.0500"),
        amount=Decimal("1000.00"),
        customer_ref="CUST-1",
        status=ApprovalStatus.PENDING,
        expires_at=datetime.now(UTC) + expires_delta,
    )
    async with unit_of_work() as conn:
        await approval_repo.create_pending(conn, approval)
    return approval.approval_id


def _state(approval_id: str, decision: dict[str, object], requested: str) -> dict[str, object]:
    return {
        "pending_approval_id": approval_id,
        "approval_decision": decision,
        "price_quote": _QUOTE,
        "requested_quantity": 2,
        "requested_discount": requested,
    }


async def test_approve_applies_requested(db: None) -> None:
    aid = await _seed(requested="0.20", expires_delta=timedelta(hours=1))
    out = await apply_decision_node(_state(aid, {"decision": "approve"}, "0.20"))  # type: ignore[arg-type]
    assert out["final_outcome"] == "approved"
    assert "20%" in out["reply"]
    assert "800.00" in out["reply"]


async def test_override_clamped_to_requested(db: None) -> None:
    aid = await _seed(requested="0.25", expires_delta=timedelta(hours=1))
    lower = await apply_decision_node(
        _state(aid, {"decision": "approve_with_override", "discount_pct": "0.18"}, "0.25")  # type: ignore[arg-type]
    )
    assert lower["final_outcome"] == "overridden"
    assert "18%" in lower["reply"]

    aid2 = await _seed(requested="0.25", expires_delta=timedelta(hours=1))
    clamped = await apply_decision_node(
        _state(aid2, {"decision": "approve_with_override", "discount_pct": "0.40"}, "0.25")  # type: ignore[arg-type]
    )
    assert "25%" in clamped["reply"]


async def test_reject_offers_in_policy_price(db: None) -> None:
    aid = await _seed(requested="0.30", expires_delta=timedelta(hours=1))
    out = await apply_decision_node(_state(aid, {"decision": "reject"}, "0.30"))  # type: ignore[arg-type]
    assert out["final_outcome"] == "rejected"
    assert "1000.00" in out["reply"]
    assert "desconto" in out["reply"].lower()


async def test_expired_overrides_any_decision(db: None) -> None:
    aid = await _seed(requested="0.20", expires_delta=timedelta(hours=-1))
    out = await apply_decision_node(_state(aid, {"decision": "approve"}, "0.20"))  # type: ignore[arg-type]
    assert out["final_outcome"] == "expired"
    assert "1000.00" in out["reply"]


def test_module_does_not_import_llm() -> None:
    source = Path(apply_decision_node.__code__.co_filename).read_text(encoding="utf-8")
    assert "services.llm" not in source
    assert "import llm" not in source
