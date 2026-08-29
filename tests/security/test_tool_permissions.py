ALLOWED = {
    "recommendation": {
        "search_products",
        "get_product_details",
        "get_inventory",
        "get_customer_sales_context",
    },
    "negotiation": {"get_price", "calculate_margin", "propose_allowed_discount"},
    "checkout": {"get_quote", "get_inventory", "get_price", "create_quote", "create_order", "create_payment_sandbox"},
    "opportunity": {"get_customer_sales_context", "find_opportunities", "create_opportunity"},
}

def test_recommendation_agent_has_no_write_tools() -> None:
    forbidden = {"create_quote", "create_order", "create_payment_sandbox", "set_discount"}
    assert ALLOWED["recommendation"].isdisjoint(forbidden)

def test_no_agent_has_generic_set_discount() -> None:
    assert all("set_discount" not in tools for tools in ALLOWED.values())

def test_opportunity_agent_cannot_send_whatsapp_directly() -> None:
    assert "send_whatsapp_direct" not in ALLOWED["opportunity"]
