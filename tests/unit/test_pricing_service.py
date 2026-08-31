import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from revenueflow.domain.models import MarginBreakdown, PriceQuote
from revenueflow.services.pricing import calculate_margin, get_price

_SEEDS = Path(__file__).resolve().parents[2] / "seeds"
_WITH_ROW = "PMP-100-CEN"
_WITHOUT_ROW = "PMP-100-PER"


def _customer_pricing(product_id: str) -> tuple[Decimal, Decimal]:
    rows: list[dict[str, Any]] = json.loads(
        (_SEEDS / "customer_pricing.json").read_text(encoding="utf-8")
    )
    row = next(r for r in rows if r["product_id"] == product_id and r["customer_id"] == "CUST-001")
    return Decimal(str(row["negotiated_price"])), Decimal(str(row["max_discount_pct"]))


def _list_price(product_id: str, quantity: int) -> Decimal:
    rows: list[dict[str, Any]] = json.loads((_SEEDS / "products.json").read_text(encoding="utf-8"))
    product = next(r for r in rows if r["product_id"] == product_id)
    best = Decimal("0")
    for tier in sorted(product["price_tiers"], key=lambda t: int(t["min_qty"])):
        if quantity >= int(tier["min_qty"]):
            best = Decimal(str(tier["unit_price"]))
    return best


async def test_get_price_uses_customer_pricing_when_row_exists(db: None) -> None:
    negotiated, max_discount = _customer_pricing(_WITH_ROW)
    quote = await get_price("CUST-001", _WITH_ROW, 10)

    assert isinstance(quote, PriceQuote)
    assert quote.customer_price == negotiated
    assert quote.maximum_discount is not None
    assert quote.maximum_discount == max_discount


async def test_get_price_falls_back_to_list_price_without_row(db: None) -> None:
    quote = await get_price("CUST-999", _WITHOUT_ROW, 10)

    assert quote.customer_price == _list_price(_WITHOUT_ROW, 10)
    assert quote.customer_price == quote.list_price
    assert quote.maximum_discount is None


async def test_get_price_with_none_customer_ref_falls_back(db: None) -> None:
    quote = await get_price(None, _WITHOUT_ROW, 10)

    assert quote.customer_price == quote.list_price
    assert quote.maximum_discount is None


async def test_get_price_unknown_product_raises_lookup_error(db: None) -> None:
    with pytest.raises(LookupError):
        await get_price(None, "PMP-DOES-NOT-EXIST", 1)


def test_calculate_margin_is_exact() -> None:
    breakdown = calculate_margin(Decimal("100"), Decimal("70"), Decimal("0.10"))

    assert isinstance(breakdown, MarginBreakdown)
    assert breakdown.revenue == Decimal("90.00")
    assert breakdown.cost == Decimal("70.00")
    assert breakdown.gross_profit == Decimal("20.00")
    assert breakdown.margin == Decimal("0.2222")


async def test_get_price_is_deterministic(db: None) -> None:
    first = await get_price("CUST-001", _WITH_ROW, 10)
    for _ in range(50):
        again = await get_price("CUST-001", _WITH_ROW, 10)
        assert again.product_id == first.product_id
        assert again.list_price == first.list_price
        assert again.customer_price == first.customer_price
        assert again.unit_cost == first.unit_cost
        assert again.maximum_discount == first.maximum_discount
        assert again.minimum_margin == first.minimum_margin
        assert again.valid_until == first.valid_until
