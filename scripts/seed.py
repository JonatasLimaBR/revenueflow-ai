import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from revenueflow.config import get_settings

SEEDS_DIR = Path(__file__).resolve().parents[1] / "seeds"

UPSERT_PRODUCT = """
INSERT INTO sim_product (product_id, name, category, attrs, price_tiers)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (product_id) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    attrs = EXCLUDED.attrs,
    price_tiers = EXCLUDED.price_tiers
"""

UPSERT_INVENTORY = """
INSERT INTO sim_inventory (product_id, available, reserved, lead_time_days)
VALUES (%s, %s, %s, %s)
ON CONFLICT (product_id) DO UPDATE SET
    available = EXCLUDED.available,
    reserved = EXCLUDED.reserved,
    lead_time_days = EXCLUDED.lead_time_days
"""

UPSERT_CUSTOMER_SALES = """
INSERT INTO sim_customer_sales (customer_id, product_id, last_qty, last_order_at)
VALUES (%s, %s, %s, %s)
ON CONFLICT (customer_id, product_id) DO UPDATE SET
    last_qty = EXCLUDED.last_qty,
    last_order_at = EXCLUDED.last_order_at
"""

UPDATE_PRODUCT_COST = """
UPDATE sim_product SET unit_cost = %s, min_margin_pct = %s WHERE product_id = %s
"""

UPSERT_CUSTOMER_PRICING = """
INSERT INTO sim_customer_pricing (customer_id, product_id, negotiated_price, max_discount_pct)
VALUES (%s, %s, %s, %s)
ON CONFLICT (customer_id, product_id) DO UPDATE SET
    negotiated_price = EXCLUDED.negotiated_price,
    max_discount_pct = EXCLUDED.max_discount_pct
"""


def _load(name: str) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads((SEEDS_DIR / name).read_text(encoding="utf-8"))
    return payload


def main() -> int:
    products = _load("products.json")
    inventory = _load("inventory.json")
    customer_sales = _load("customer_sales.json")
    product_cost = _load("product_cost.json")
    customer_pricing = _load("customer_pricing.json")

    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            for product in products:
                cur.execute(
                    UPSERT_PRODUCT,
                    (
                        product["product_id"],
                        product["name"],
                        product["category"],
                        Jsonb(product["attrs"]),
                        Jsonb(product["price_tiers"]),
                    ),
                )
            for row in inventory:
                cur.execute(
                    UPSERT_INVENTORY,
                    (
                        row["product_id"],
                        row["available"],
                        row["reserved"],
                        row["lead_time_days"],
                    ),
                )
            for sale in customer_sales:
                cur.execute(
                    UPSERT_CUSTOMER_SALES,
                    (
                        sale["customer_id"],
                        sale["product_id"],
                        sale["last_qty"],
                        sale["last_order_at"],
                    ),
                )
            for cost in product_cost:
                cur.execute(
                    UPDATE_PRODUCT_COST,
                    (
                        Decimal(str(cost["unit_cost"])),
                        Decimal(str(cost["min_margin_pct"])),
                        cost["product_id"],
                    ),
                )
            for pricing in customer_pricing:
                cur.execute(
                    UPSERT_CUSTOMER_PRICING,
                    (
                        pricing["customer_id"],
                        pricing["product_id"],
                        Decimal(str(pricing["negotiated_price"])),
                        Decimal(str(pricing["max_discount_pct"])),
                    ),
                )
        conn.commit()

    print(
        f"seeded sim_product={len(products)} sim_inventory={len(inventory)} "
        f"sim_customer_sales={len(customer_sales)} product_cost={len(product_cost)} "
        f"sim_customer_pricing={len(customer_pricing)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
