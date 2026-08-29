"""Recommendation Agent tool registry -- the security boundary (D5, SPEC-024/025).

``RECOMMENDATION_TOOLS`` is the explicit allowlist of tools the Recommendation
Agent may call. Every entry is read-only. No ``set_discount``, ``create_quote``,
``create_order``, ``create_payment_sandbox``, ``send_whatsapp_direct``, or any
other write tool belongs here. Granting write capability to this agent requires
a reviewed code change and a new ADR, not a config toggle.
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
