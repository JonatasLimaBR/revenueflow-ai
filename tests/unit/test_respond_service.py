from revenueflow.domain.models import Intent
from revenueflow.services import generate


async def test_generate_grounds_reply_in_tool_results() -> None:
    text = await generate(
        intent=Intent.PRODUCT_SEARCH,
        customer_text="quero uma bomba 1cv",
        tool_results=[
            {"name": "Bomba periférica 1CV", "price_from": 450.0, "available": 12},
        ],
    )

    assert "Bomba periférica 1CV" in text
    assert "450" not in text
    assert "R$" not in text


async def test_generate_uses_fixed_fallback_without_tool_results() -> None:
    first = await generate(
        intent=Intent.PRODUCT_SEARCH,
        customer_text="tem alguma coisa?",
        tool_results=[],
    )
    second = await generate(
        intent=Intent.ORDER_STATUS,
        customer_text="e o meu pedido?",
        tool_results=[],
    )

    assert first == second
    assert "humano" in first.lower()
