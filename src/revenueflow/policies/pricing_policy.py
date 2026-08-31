from __future__ import annotations

from decimal import Decimal

from revenueflow.domain.models import PolicyDecision, PolicyReason

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _margin(price: Decimal, unit_cost: Decimal) -> Decimal:
    if price <= _ZERO:
        return _ZERO
    return (price - unit_cost) / price


def evaluate(
    *,
    customer_price: Decimal,
    unit_cost: Decimal,
    requested_discount: Decimal,
    minimum_margin: Decimal,
    maximum_discount: Decimal,
) -> PolicyDecision:
    requested = max(_ZERO, min(requested_discount, _ONE))
    resulting_price = customer_price * (_ONE - requested)
    resulting_margin = _margin(resulting_price, unit_cost)
    over_discount = requested > maximum_discount
    under_margin = resulting_margin < minimum_margin
    requires_approval = over_discount or under_margin
    if customer_price > _ZERO and (_ONE - minimum_margin) > _ZERO:
        max_by_margin = _ONE - (unit_cost / (customer_price * (_ONE - minimum_margin)))
    else:
        max_by_margin = _ZERO
    max_allowed = max(_ZERO, min(maximum_discount, max_by_margin))
    reason = (
        PolicyReason.MARGIN_BELOW_MINIMUM
        if under_margin
        else PolicyReason.DISCOUNT_OUT_OF_POLICY
        if over_discount
        else PolicyReason.WITHIN_POLICY
    )
    return PolicyDecision(
        allowed=not requires_approval,
        max_allowed=max_allowed.quantize(Decimal("0.0001")),
        resulting_margin=resulting_margin.quantize(Decimal("0.0001")),
        requires_approval=requires_approval,
        reason=reason,
    )
