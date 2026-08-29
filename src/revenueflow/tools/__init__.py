"""Read-only tool boundary for the Recommendation Agent (D5, SPEC-024/025)."""

from revenueflow.tools.catalog import (
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)
from revenueflow.tools.registry import RECOMMENDATION_TOOL_NAMES, RECOMMENDATION_TOOLS
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
    "RECOMMENDATION_TOOLS",
    "RECOMMENDATION_TOOL_NAMES",
    "CustomerSalesInput",
    "InventoryInput",
    "InventoryView",
    "ProductDetailsInput",
    "ProductSummary",
    "SalesRow",
    "SearchProductsInput",
    "get_customer_sales_context",
    "get_inventory",
    "get_product_details",
    "search_products",
]
