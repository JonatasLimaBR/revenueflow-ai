"""Tool boundary for the Recommendation and Negotiation Agents (D5, SPEC-024/025)."""

from revenueflow.tools.catalog import (
    get_customer_360,
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)
from revenueflow.tools.checkout import create_order, create_payment_sandbox, create_quote
from revenueflow.tools.pricing import calculate_margin, get_price, propose_allowed_discount
from revenueflow.tools.registry import (
    CHECKOUT_TOOL_NAMES,
    CHECKOUT_TOOLS,
    NEGOTIATION_TOOL_NAMES,
    NEGOTIATION_TOOLS,
    RECOMMENDATION_TOOL_NAMES,
    RECOMMENDATION_TOOLS,
)
from revenueflow.tools.schemas import (
    Customer360Input,
    Customer360View,
    CustomerSalesInput,
    InventoryInput,
    InventoryView,
    OpenQuotes,
    ProductDetailsInput,
    ProductSummary,
    SalesRow,
    SearchProductsInput,
)

__all__ = [
    "CHECKOUT_TOOLS",
    "CHECKOUT_TOOL_NAMES",
    "NEGOTIATION_TOOLS",
    "NEGOTIATION_TOOL_NAMES",
    "RECOMMENDATION_TOOLS",
    "RECOMMENDATION_TOOL_NAMES",
    "Customer360Input",
    "Customer360View",
    "CustomerSalesInput",
    "InventoryInput",
    "InventoryView",
    "OpenQuotes",
    "ProductDetailsInput",
    "ProductSummary",
    "SalesRow",
    "SearchProductsInput",
    "calculate_margin",
    "create_order",
    "create_payment_sandbox",
    "create_quote",
    "get_customer_360",
    "get_customer_sales_context",
    "get_inventory",
    "get_price",
    "get_product_details",
    "propose_allowed_discount",
    "search_products",
]
