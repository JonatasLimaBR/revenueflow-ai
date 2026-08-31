from decimal import Decimal

import pytest

from revenueflow.services.negotiation import PriceAsk, extract_price_ask


@pytest.mark.parametrize(
    ("text", "discount", "target_price", "quantity"),
    [
        ("consegue 15%?", Decimal("0.15"), None, None),
        ("quero quinze por cento de desconto", Decimal("0.15"), None, None),
        ("preciso de 50 unidades", None, None, 50),
        ("consegue 20 por cento em 100 pecas", Decimal("0.20"), None, 100),
        ("quero uma bomba", None, None, None),
        ("faz por R$ 1.200?", None, Decimal("1200"), None),
        ("1.200,00 reais", None, Decimal("1200.00"), None),
        ("faço por 950 em 100 unidades", None, Decimal("950"), 100),
        ("quero 50 unidades", None, None, 50),
    ],
)
def test_extract_price_ask_cases(
    text: str,
    discount: Decimal | None,
    target_price: Decimal | None,
    quantity: int | None,
) -> None:
    ask = extract_price_ask(text)
    assert ask.discount == discount
    assert ask.target_price == target_price
    assert ask.quantity == quantity


def test_extract_price_ask_ignores_bare_number_words() -> None:
    assert extract_price_ask("quero cinco bombas") == PriceAsk()


def test_extract_price_ask_handles_pecas_with_cedilla() -> None:
    assert extract_price_ask("faço 30 peças") == PriceAsk(quantity=30)
