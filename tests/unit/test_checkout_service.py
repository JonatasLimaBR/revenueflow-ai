from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from revenueflow.domain.models import Order, OrderStatus, Quote, QuoteStatus
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories.db import fetchall, unit_of_work
from revenueflow.services import checkout as checkout_svc
from revenueflow.tools import create_payment_sandbox
from revenueflow.tools.catalog import search_products


def _state(product: dict[str, object], quantity: int) -> dict[str, object]:
    return {
        "conversation_id": f"c-{uuid4().hex}",
        "customer_id": None,
        "customer_text": "quero fechar",
        "price_quote": {"customer_price": "1000.00", "valid_until": "2026-12-31T00:00:00+00:00"},
        "requested_quantity": quantity,
        "checkout_discount": "0.10",
        "tool_results": [{"tool": "search_products", "result": [product]}],
    }


async def _seed_quote(product: dict[str, object], quantity: int) -> Quote:
    quote = Quote(
        quote_id=uuid4().hex,
        conversation_id=f"c-{uuid4().hex}",
        customer_ref=None,
        items=[
            {
                "product_id": product["product_id"],
                "name": product["name"],
                "quantity": quantity,
                "unit_price": "900.00",
                "discount": "0.10",
            }
        ],
        total=Decimal("900.00") * quantity,
        expiration=datetime.now(UTC) + timedelta(days=1),
        status=QuoteStatus.SENT,
    )
    async with unit_of_work() as conn:
        return await checkout_repo.create_quote(conn, quote)


async def test_quote_from_state_prices_from_pricing_tools(db: None) -> None:
    product = (await search_products("1cv"))[0]
    quote = await checkout_svc.quote_from_state(_state(product, 3))
    assert quote.status is QuoteStatus.SENT
    assert quote.items[0]["product_id"] == product["product_id"]
    assert quote.total == Decimal("2700.00")  # 1000 * (1 - 0.10) * 3


async def test_create_order_is_idempotent_on_quote_id(db: None) -> None:
    product = (await search_products("1cv"))[0]
    quote = await _seed_quote(product, 1)
    order = Order(
        order_id=uuid4().hex,
        quote_id=quote.quote_id,
        customer_ref=None,
        items=quote.items,
        total=quote.total,
        status=OrderStatus.CONFIRMED,
    )
    async with unit_of_work() as conn:
        first = await checkout_repo.create_order(conn, order)
        second = await checkout_repo.create_order(
            conn,
            Order(
                order_id=uuid4().hex,
                quote_id=quote.quote_id,
                customer_ref=None,
                items=quote.items,
                total=quote.total,
                status=OrderStatus.CONFIRMED,
            ),
        )
        rows = await fetchall(
            conn, "SELECT order_id FROM sales_order WHERE quote_id = %s", (quote.quote_id,)
        )
    assert first.order_id == second.order_id
    assert len(rows) == 1


async def test_confirm_out_of_stock_expires_quote(db: None) -> None:
    product = (await search_products("1cv"))[0]
    quote = await _seed_quote(product, 999_999)
    outcome = await checkout_svc.confirm(quote)
    assert outcome["outcome"] == "out_of_stock"
    async with unit_of_work() as conn:
        rows = await fetchall(
            conn, "SELECT status FROM quote WHERE quote_id = %s", (quote.quote_id,)
        )
        orders = await fetchall(
            conn, "SELECT 1 FROM sales_order WHERE quote_id = %s", (quote.quote_id,)
        )
    assert rows[0]["status"] == "EXPIRED"
    assert orders == []


async def test_payment_sandbox_stores_only_amount_and_order(db: None) -> None:
    res = await create_payment_sandbox("ord-test", Decimal("123.45"))
    assert res["status"] == "APPROVED"
    async with unit_of_work() as conn:
        cols = await fetchall(
            conn,
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'payment'",
        )
    names = {c["column_name"] for c in cols}
    assert names == {"payment_id", "order_id", "amount", "status", "created_at"}
