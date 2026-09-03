from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from revenueflow.domain.models import OpportunityStatus, OpportunityType
from revenueflow.policies.opportunity_policy import (
    QuoteRecoverySignal,
    ReplenishmentSignal,
    quote_recovery,
    replenishment,
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
