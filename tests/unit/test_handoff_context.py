import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from revenueflow.domain.models import Opportunity, OpportunityStatus, OpportunityType
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services.handoff import build_context

_KEYS = {
    "conversation_summary",
    "customer",
    "intent",
    "products",
    "quote",
    "objections",
    "reason",
    "next_best_action",
}


def _state(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "conversation_id": f"c-{uuid4().hex}",
        "customer_id": None,
        "intent": "price_request",
        "handoff_reason": "high_value_order",
        "tool_results": [
            {"tool": "search_products", "result": [{"product_id": "P1", "name": "Bomba 1CV"}]}
        ],
        "price_quote": {"customer_price": "1000.00", "valid_until": "2026-12-31T00:00:00+00:00"},
        "requested_discount": "0.20",
    }
    base.update(overrides)
    return base


async def test_context_has_eight_keys_from_state(db: None) -> None:
    ctx = await build_context(_state())

    assert set(ctx) == _KEYS
    assert ctx["products"] == [{"product_id": "P1", "name": "Bomba 1CV"}]
    assert ctx["quote"] == {
        "customer_price": "1000.00",
        "valid_until": "2026-12-31T00:00:00+00:00",
    }
    assert ctx["objections"] == ["desconto solicitado 0.20"]
    assert ctx["reason"] == "high_value_order"
    assert ctx["conversation_summary"]


async def test_context_without_customer_or_opportunity(db: None) -> None:
    ctx = await build_context(_state(customer_id=None))

    assert ctx["customer"] is None
    assert ctx["next_best_action"] is None
    assert set(ctx) == _KEYS


async def test_context_uses_open_opportunity_for_next_best_action(db: None) -> None:
    customer_id = f"CUST-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await opportunity_repo.upsert_open(
            conn,
            Opportunity(
                opportunity_id=uuid4().hex,
                customer_id=customer_id,
                opportunity_type=OpportunityType.REPLENISHMENT,
                product="P1",
                estimated_revenue=Decimal("500"),
                probability=Decimal("0.35"),
                reason="teste",
                evidence={"threshold": 1.5},
                recommended_action="offer_replenishment",
                status=OpportunityStatus.OPEN,
                created_at=datetime.now(UTC),
            ),
        )

    ctx = await build_context(_state(customer_id=customer_id))
    assert ctx["next_best_action"] == "offer_replenishment"


async def test_context_is_json_safe(db: None) -> None:
    ctx = await build_context(_state())
    json.dumps(ctx)
