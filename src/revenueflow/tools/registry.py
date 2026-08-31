"""Agent tool registries -- the security boundary (D5, SPEC-024/025).

``RECOMMENDATION_TOOLS`` and ``NEGOTIATION_TOOLS`` are the explicit allowlists of
tools each agent may call. Every entry is read-only or deterministic. No
``set_discount``, ``create_quote``, ``create_order``, ``create_payment_sandbox``,
``send_whatsapp_direct``, or any other write tool belongs in either list, and the
Negotiation Agent in particular gets no ``set_discount`` and no ``create_*``.
Widening any registry requires a reviewed code change and a new ADR, not a config
toggle.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Final

from revenueflow.tools.catalog import (
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)
from revenueflow.tools.pricing import calculate_margin, get_price, propose_allowed_discount

RECOMMENDATION_TOOLS: Final[list[Callable[..., Awaitable[Any]]]] = [
    search_products,
    get_product_details,
    get_inventory,
    get_customer_sales_context,
]

RECOMMENDATION_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {
        search_products.__name__,
        get_product_details.__name__,
        get_inventory.__name__,
        get_customer_sales_context.__name__,
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
