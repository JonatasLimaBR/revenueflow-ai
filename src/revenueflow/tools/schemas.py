"""Pydantic models for the read-only recommendation tool boundary.

Each tool has an explicit input model and an explicit output model. The output
models are what nodes hand to the grounding step (SPEC-029): a reply may only
cite fields that appear here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SearchProductsInput(BaseModel):
    """Arguments for :func:`revenueflow.tools.catalog.search_products`."""

    query: str
    limit: int = 5


class ProductSummary(BaseModel):
    """A single catalog row returned by product search or product detail."""

    product_id: str
    name: str
    category: str
    attrs: dict[str, Any]
    price_tiers: list[dict[str, Any]]


class ProductDetailsInput(BaseModel):
    """Arguments for :func:`revenueflow.tools.catalog.get_product_details`."""

    product_id: str


class InventoryInput(BaseModel):
    """Arguments for :func:`revenueflow.tools.catalog.get_inventory`."""

    product_id: str
    quantity: int = 1


class InventoryView(BaseModel):
    """Availability snapshot for one product."""

    product_id: str
    available: int
    fulfillable: bool
    lead_time_days: int | None


class CustomerSalesInput(BaseModel):
    """Arguments for :func:`revenueflow.tools.catalog.get_customer_sales_context`."""

    customer_id: str
    limit: int = 10


class SalesRow(BaseModel):
    """One prior-order row for a known customer."""

    product_id: str
    last_qty: int
    last_order_at: datetime


class Customer360Input(BaseModel):
    """Arguments for :func:`revenueflow.tools.catalog.get_customer_360`."""

    customer_id: str


class OpenQuotes(BaseModel):
    """Open quotes for a known customer."""

    count: int
    quote_ids: list[str]


class Customer360View(BaseModel):
    """Bounded commercial view for a known customer (SPEC-017, ADR-033)."""

    orders_12m: int
    revenue_12m: Decimal
    average_ticket: Decimal
    last_purchase: datetime | None
    purchase_interval_days: float | None
    preferred_products: list[str]
    open_quotes: OpenQuotes
