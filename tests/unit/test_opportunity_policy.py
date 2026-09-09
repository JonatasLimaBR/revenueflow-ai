from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from revenueflow.domain.models import OpportunityStatus, OpportunityType
from revenueflow.policies.opportunity_policy import (
    CrossSellSignal,
    InventoryToCashSignal,
    OrderRecoverySignal,
    QuoteRecoverySignal,
    ReplenishmentSignal,
    UpsellSignal,
    churn,
    cross_sell,
    inventory_to_cash,
    order_recovery,
    quote_recovery,
    reactivation,
    replenishment,
    upsell,
)

_NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _rep(days: float, interval: float) -> ReplenishmentSignal:
    return ReplenishmentSignal(
        customer_id="CUST-X",
        product_id="P1",
        days_since_last_purchase=days,
        average_purchase_interval=interval,
        average_ticket=Decimal("500.00"),
    )


def test_replenishment_fires_when_overdue() -> None:
    opp = replenishment(_rep(100, 60), now=_NOW, threshold=Decimal("1.5"))

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.REPLENISHMENT
    assert opp.status is OpportunityStatus.OPEN
    assert opp.product == "P1"
    assert opp.estimated_revenue == Decimal("500.00")
    assert opp.probability == Decimal("0.35")
    assert opp.recommended_action == "offer_replenishment"
    assert opp.evidence["threshold"] == 1.5
    assert opp.evidence["days_since_last_purchase"] == 100
    assert opp.reason


def test_replenishment_silent_when_within_interval() -> None:
    assert replenishment(_rep(80, 60), now=_NOW, threshold=Decimal("1.5")) is None


def _quote(**kw: object) -> QuoteRecoverySignal:
    base: dict[str, object] = {
        "quote_id": "Q1",
        "customer_id": "CUST-X",
        "product_id": "P2",
        "status": "SENT",
        "created_at": _NOW - timedelta(hours=100),
        "total": Decimal("1200.00"),
        "has_order": False,
    }
    base.update(kw)
    return QuoteRecoverySignal(**base)  # type: ignore[arg-type]


def test_quote_recovery_fires_when_stale() -> None:
    opp = quote_recovery(_quote(), now=_NOW, limit_hours=72)

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.QUOTE_RECOVERY
    assert opp.product == "P2"
    assert opp.estimated_revenue == Decimal("1200.00")
    assert opp.probability == Decimal("0.45")
    assert opp.recommended_action == "follow_up_quote"
    assert opp.evidence["quote_id"] == "Q1"
    assert 99 <= opp.evidence["age_hours"] <= 101
    assert opp.reason


@pytest.mark.parametrize(
    "override",
    [
        {"status": "ACCEPTED"},
        {"created_at": _NOW - timedelta(hours=10)},
        {"has_order": True},
    ],
)
def test_quote_recovery_silent(override: dict[str, object]) -> None:
    assert quote_recovery(_quote(**override), now=_NOW, limit_hours=72) is None


def test_churn_fires_past_its_own_higher_threshold() -> None:
    opp = churn(_rep(200, 60), now=_NOW, threshold=Decimal("3.0"))

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.CHURN
    assert opp.product is None
    assert opp.probability == Decimal("0.25")
    assert opp.recommended_action == "reengagement_outreach"


def test_churn_silent_below_threshold() -> None:
    assert churn(_rep(100, 60), now=_NOW, threshold=Decimal("3.0")) is None


def test_reactivation_fires_past_its_own_higher_threshold() -> None:
    opp = reactivation(_rep(400, 60), now=_NOW, threshold=Decimal("6.0"))

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.REACTIVATION
    assert opp.product is None
    assert opp.probability == Decimal("0.15")
    assert opp.recommended_action == "win_back_campaign"


def test_reactivation_silent_below_threshold() -> None:
    assert reactivation(_rep(200, 60), now=_NOW, threshold=Decimal("6.0")) is None


def _order_recovery_signal(**kw: object) -> OrderRecoverySignal:
    base: dict[str, object] = {
        "order_id": "O1",
        "customer_id": "CUST-X",
        "product_id": "P3",
        "total": Decimal("900.00"),
        "failed_at": _NOW - timedelta(hours=48),
    }
    base.update(kw)
    return OrderRecoverySignal(**base)  # type: ignore[arg-type]


def test_order_recovery_fires_when_old_enough() -> None:
    opp = order_recovery(_order_recovery_signal(), now=_NOW, min_age_hours=24)

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.ORDER_RECOVERY
    assert opp.product == "P3"
    assert opp.estimated_revenue == Decimal("900.00")
    assert opp.probability == Decimal("0.40")
    assert opp.recommended_action == "retry_payment_offer"
    assert opp.evidence["order_id"] == "O1"


def test_order_recovery_silent_when_too_recent() -> None:
    signal = _order_recovery_signal(failed_at=_NOW - timedelta(hours=10))
    assert order_recovery(signal, now=_NOW, min_age_hours=24) is None


def test_cross_sell_always_fires() -> None:
    signal = CrossSellSignal(
        customer_id="CUST-X",
        complement_product_id="ACC-CAP-250",
        complement_price=Decimal("39.90"),
        purchased_category="bomba d'água periférica",
    )
    opp = cross_sell(signal, now=_NOW)

    assert opp.opportunity_type is OpportunityType.CROSS_SELL
    assert opp.product == "ACC-CAP-250"
    assert opp.estimated_revenue == Decimal("39.90")
    assert opp.probability == Decimal("0.20")
    assert opp.recommended_action == "offer_accessory"


def _upsell_signal(**kw: object) -> UpsellSignal:
    base: dict[str, object] = {
        "customer_id": "CUST-X",
        "current_product_id": "PMP-033-PER",
        "repeat_count": 2,
        "upgrade_product_id": "PMP-050-PER",
        "upgrade_price": Decimal("389.90"),
    }
    base.update(kw)
    return UpsellSignal(**base)  # type: ignore[arg-type]


def test_upsell_fires_at_min_repeat_purchases() -> None:
    opp = upsell(_upsell_signal(), now=_NOW, min_repeat_purchases=2)

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.UPSELL
    assert opp.product == "PMP-050-PER"
    assert opp.estimated_revenue == Decimal("389.90")
    assert opp.probability == Decimal("0.20")
    assert opp.recommended_action == "offer_upgrade"


def test_upsell_silent_below_min_repeat_purchases() -> None:
    signal = _upsell_signal(repeat_count=1)
    assert upsell(signal, now=_NOW, min_repeat_purchases=2) is None


def _inventory_signal(**kw: object) -> InventoryToCashSignal:
    base: dict[str, object] = {
        "customer_id": "CUST-X",
        "product_id": "PMP-100-CEN",
        "available": 50,
        "stale_days": 90,
        "unit_price": Decimal("729.90"),
    }
    base.update(kw)
    return InventoryToCashSignal(**base)  # type: ignore[arg-type]


def test_inventory_to_cash_fires_past_both_thresholds() -> None:
    opp = inventory_to_cash(
        _inventory_signal(), now=_NOW, stock_threshold=10, stale_days_threshold=60
    )

    assert opp is not None
    assert opp.opportunity_type is OpportunityType.INVENTORY_TO_CASH
    assert opp.product == "PMP-100-CEN"
    assert opp.estimated_revenue == Decimal("729.90")
    assert opp.probability == Decimal("0.15")
    assert opp.recommended_action == "offer_clearance"


@pytest.mark.parametrize(
    "override",
    [
        {"available": 5},
        {"stale_days": 10},
    ],
)
def test_inventory_to_cash_silent_below_either_threshold(override: dict[str, object]) -> None:
    signal = _inventory_signal(**override)
    assert inventory_to_cash(signal, now=_NOW, stock_threshold=10, stale_days_threshold=60) is None


def test_policy_module_is_pure() -> None:
    source = Path("src/revenueflow/policies/opportunity_policy.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.services" not in import_lines
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.adapters" not in import_lines
    assert "revenueflow.repositories" not in import_lines
