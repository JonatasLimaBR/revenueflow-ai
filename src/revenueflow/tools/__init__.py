"""Tool boundary for the Recommendation and Negotiation Agents (D5, SPEC-024/025)."""

from revenueflow.tools.catalog import (
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)
from revenueflow.tools.pricing import calculate_margin, get_price, propose_allowed_discount
from revenueflow.tools.registry import (
    NEGOTIATION_TOOL_NAMES,
    NEGOTIATION_TOOLS,
    RECOMMENDATION_TOOL_NAMES,
    RECOMMENDATION_TOOLS,
)
from revenueflow.tools.schemas import (
    CustomerSalesInput,
    InventoryInput,
    InventoryView,
    ProductDetailsInput,
    ProductSummary,
    SalesRow,
    SearchProductsInput,
)

__all__ = [
    "NEGOTIATION_TOOLS",
    "NEGOTIATION_TOOL_NAMES",
    "RECOMMENDATION_TOOLS",
    "RECOMMENDATION_TOOL_NAMES",
    "CustomerSalesInput",
    "InventoryInput",
    "InventoryView",
    "ProductDetailsInput",
    "ProductSummary",
    "SalesRow",
    "SearchProductsInput",
    "calculate_margin",
    "get_customer_sales_context",
    "get_inventory",
    "get_price",
    "get_product_details",
    "propose_allowed_discount",
    "search_products",
]
