from decimal import Decimal

import pytest

from revenueflow.domain.models import PolicyDecision
from revenueflow.policies.pricing_policy import evaluate

_ZERO = Decimal("0")
_ONE = Decimal("1")
_REASONS = {"margin_below_minimum", "discount_out_of_policy", "within_policy"}

_CASES = [
    (Decimal("100"), Decimal("60"), Decimal("0.05"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("60"), Decimal("0.20"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("90"), Decimal("0.08"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("95"), Decimal("0.50"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("80"), Decimal("0"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("80"), Decimal("-0.10"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("70"), Decimal("0.10"), Decimal("0.15"), Decimal("0.10")),
    (Decimal("100"), Decimal("99"), Decimal("0.30"), Decimal("0.15"), Decimal("0.20")),
    (Decimal("500"), Decimal("300"), Decimal("0.12"), Decimal("0.20"), Decimal("0.15")),
    (Decimal("1200"), Decimal("700"), Decimal("0.03"), Decimal("0.15"), Decimal("0.10")),
]


@pytest.mark.parametrize(
    ("customer_price", "unit_cost", "requested_discount", "minimum_margin", "maximum_discount"),
    _CASES,
)
def test_evaluate_matrix(
    customer_price: Decimal,
    unit_cost: Decimal,
    requested_discount: Decimal,
    minimum_margin: Decimal,
    maximum_discount: Decimal,
) -> None:
    decision = evaluate(
        customer_price=customer_price,
        unit_cost=unit_cost,
        requested_discount=requested_discount,
        minimum_margin=minimum_margin,
        maximum_discount=maximum_discount,
    )
    assert isinstance(decision, PolicyDecision)

    requested = max(_ZERO, min(requested_discount, _ONE))
    resulting_price = customer_price * (_ONE - requested)
    resulting_margin = (
        (resulting_price - unit_cost) / resulting_price if resulting_price > _ZERO else _ZERO
    )
    under_margin = resulting_margin < minimum_margin
    over_discount = requested > maximum_discount
    requires_approval = under_margin or over_discount

    assert decision.requires_approval is requires_approval
    assert decision.allowed is (not requires_approval)
    assert decision.max_allowed >= _ZERO
    assert decision.reason in _REASONS
    if under_margin:
        assert decision.reason == "margin_below_minimum"
    elif over_discount:
        assert decision.reason == "discount_out_of_policy"
    else:
        assert decision.reason == "within_policy"


def test_clearly_in_policy() -> None:
    decision = evaluate(
        customer_price=Decimal("100"),
        unit_cost=Decimal("50"),
        requested_discount=Decimal("0.02"),
        minimum_margin=Decimal("0.15"),
        maximum_discount=Decimal("0.10"),
    )
    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.reason == "within_policy"
    assert decision.max_allowed >= _ZERO


def test_clearly_out_of_policy() -> None:
    decision = evaluate(
        customer_price=Decimal("100"),
        unit_cost=Decimal("95"),
        requested_discount=Decimal("0.40"),
        minimum_margin=Decimal("0.15"),
        maximum_discount=Decimal("0.10"),
    )
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.reason == "margin_below_minimum"
    assert decision.max_allowed >= _ZERO
