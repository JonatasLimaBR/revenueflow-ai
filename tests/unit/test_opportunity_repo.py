from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from revenueflow.domain.models import Opportunity, OpportunityStatus, OpportunityType
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories.db import execute, unit_of_work

_INSERT_PRODUCT = """
INSERT INTO sim_product (product_id, name, category, price_tiers)
VALUES (%s, %s, %s, %s::jsonb)
"""

_INSERT_INVENTORY = """
INSERT INTO sim_inventory (product_id, available)
VALUES (%s, %s)
"""

_INSERT_SIM_SALE = """
INSERT INTO sim_customer_sales (customer_id, product_id, last_qty, last_order_at)
VALUES (%s, %s, 1, now() - interval '10 days')
"""

_INSERT_SIM_ORDER_WITH_ITEM = """
INSERT INTO sim_customer_order (customer_id, order_id, total, ordered_at, items)
VALUES (%s, %s, %s, now() - interval '10 days', %s::jsonb)
"""

_INSERT_FAILED_ORDER = """
INSERT INTO sales_order (order_id, quote_id, customer_ref, items, total, status, created_at)
VALUES (%s, %s, %s, %s::jsonb, %s, 'FAILED', now() - (%s || ' hours')::interval)
"""


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


async def test_order_recovery_candidates_finds_failed_order_never_retried(db: None) -> None:
    customer_id = f"CUST-OR-{uuid4().hex[:8]}"
    order_id = uuid4().hex
    async with unit_of_work() as conn:
        await execute(
            conn,
            _INSERT_FAILED_ORDER,
            (order_id, uuid4().hex, customer_id, '[{"product_id": "PMP-100-CEN"}]', "729.90", 48),
        )
        candidates = await opportunity_repo.order_recovery_candidates(conn)

    match = next(c for c in candidates if c.customer_id == customer_id)
    assert match.order_id == order_id
    assert match.product_id == "PMP-100-CEN"
    assert match.total == Decimal("729.90")


async def test_order_recovery_candidates_excludes_retried_orders(db: None) -> None:
    customer_id = f"CUST-OR-{uuid4().hex[:8]}"
    failed_id = uuid4().hex
    paid_id = uuid4().hex
    async with unit_of_work() as conn:
        await execute(
            conn,
            _INSERT_FAILED_ORDER,
            (failed_id, uuid4().hex, customer_id, '[{"product_id": "PMP-100-CEN"}]', "729.90", 48),
        )
        await execute(
            conn,
            """
            INSERT INTO sales_order
                (order_id, quote_id, customer_ref, items, total, status, created_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, 'PAID', now() - interval '1 hour')
            """,
            (paid_id, uuid4().hex, customer_id, '[{"product_id": "PMP-100-CEN"}]', "729.90"),
        )
        candidates = await opportunity_repo.order_recovery_candidates(conn)

    assert not any(c.customer_id == customer_id for c in candidates)


async def test_cross_sell_candidates_offers_the_cheapest_accessory(db: None) -> None:
    customer_id = f"CUST-XS-{uuid4().hex[:8]}"
    product_id = f"TEST-PUMP-{uuid4().hex[:8]}"
    category = f"teste-categoria-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await execute(
            conn,
            _INSERT_PRODUCT,
            (product_id, "Bomba de teste", category, '[{"min_qty": 1, "unit_price": 100.0}]'),
        )
        await execute(conn, _INSERT_SIM_SALE, (customer_id, product_id))
        candidates = await opportunity_repo.cross_sell_candidates(conn)

    match = next(c for c in candidates if c.customer_id == customer_id)
    assert match.purchased_category == category
    assert match.complement_product_id == "ACC-CAP-250"
    assert match.complement_price == Decimal("39.90")


async def test_upsell_candidates_finds_next_tier_in_category(db: None) -> None:
    customer_id = f"CUST-UP-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await execute(
            conn,
            _INSERT_SIM_ORDER_WITH_ITEM,
            (customer_id, uuid4().hex, "299.90", '[{"product_id": "PMP-033-PER"}]'),
        )
        await execute(
            conn,
            _INSERT_SIM_ORDER_WITH_ITEM,
            (customer_id, uuid4().hex, "299.90", '[{"product_id": "PMP-033-PER"}]'),
        )
        candidates = await opportunity_repo.upsell_candidates(conn)

    match = next(
        c
        for c in candidates
        if c.customer_id == customer_id and c.current_product_id == "PMP-033-PER"
    )
    assert match.repeat_count >= 2
    assert match.upgrade_product_id == "PMP-050-PER"
    assert match.upgrade_price == Decimal("389.90")


async def test_inventory_to_cash_candidates_offers_stale_stock_to_category_buyers(
    db: None,
) -> None:
    customer_id = f"CUST-ITC-{uuid4().hex[:8]}"
    product_id = f"TEST-STALE-{uuid4().hex[:8]}"
    other_product_id = f"TEST-OTHER-{uuid4().hex[:8]}"
    category = f"teste-categoria-itc-{uuid4().hex[:8]}"
    async with unit_of_work() as conn:
        await execute(
            conn,
            _INSERT_PRODUCT,
            (product_id, "Estoque parado", category, '[{"min_qty": 1, "unit_price": 199.90}]'),
        )
        await execute(conn, _INSERT_INVENTORY, (product_id, 999))
        await execute(
            conn,
            _INSERT_PRODUCT,
            (other_product_id, "Ja comprado", category, '[{"min_qty": 1, "unit_price": 50.0}]'),
        )
        await execute(conn, _INSERT_SIM_SALE, (customer_id, other_product_id))
        candidates = await opportunity_repo.inventory_to_cash_candidates(conn)

    match = next(
        c for c in candidates if c.customer_id == customer_id and c.product_id == product_id
    )
    assert match.available == 999
    assert match.stale_days > 60
    assert match.unit_price == Decimal("199.90")
