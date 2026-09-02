"""Agent tool registries -- the security boundary (D5, SPEC-024/025, ADR-037/051).

``RECOMMENDATION_TOOLS``, ``NEGOTIATION_TOOLS`` and ``CHECKOUT_TOOLS`` are the
explicit allowlists of tools each agent may call. Every entry is read-only or
deterministic. ``create_quote`` / ``create_order`` / ``create_payment_sandbox``
live only in ``CHECKOUT_TOOLS`` -- no other agent sees them -- and the checkout
tools never appear in the recommendation or negotiation lists. ``set_discount``
and ``send_whatsapp_direct`` are in no list at all. Widening any registry
requires a reviewed code change and a new ADR, not a config toggle.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Final

from revenueflow.tools.catalog import (
    get_customer_360,
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)
from revenueflow.tools.checkout import create_order, create_payment_sandbox, create_quote
from revenueflow.tools.pricing import calculate_margin, get_price, propose_allowed_discount

RECOMMENDATION_TOOLS: Final[list[Callable[..., Awaitable[Any]]]] = [
    search_products,
    get_product_details,
    get_inventory,
    get_customer_sales_context,
    get_customer_360,
]

RECOMMENDATION_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {
        search_products.__name__,
        get_product_details.__name__,
        get_inventory.__name__,
        get_customer_sales_context.__name__,
        get_customer_360.__name__,
    }
)

NEGOTIATION_TOOLS: Final[list[Callable[..., Awaitable[Any]]]] = [
    get_price,
    calculate_margin,
    propose_allowed_discount,
]

NEGOTIATION_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {get_price.__name__, calculate_margin.__name__, propose_allowed_discount.__name__}
)

CHECKOUT_TOOLS: Final[list[Callable[..., Awaitable[Any]]]] = [
    create_quote,
    create_order,
    create_payment_sandbox,
]

CHECKOUT_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {create_quote.__name__, create_order.__name__, create_payment_sandbox.__name__}
)
