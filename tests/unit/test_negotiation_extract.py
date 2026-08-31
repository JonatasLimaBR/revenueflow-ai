from decimal import Decimal

import pytest

from revenueflow.services.negotiation import extract_discount


@pytest.mark.parametrize(
    ("text", "discount", "quantity"),
    [
        ("consegue 15%?", Decimal("0.15"), None),
        ("quero quinze por cento de desconto", Decimal("0.15"), None),
        ("preciso de 50 unidades", None, 50),
        ("consegue 20 por cento em 100 pecas", Decimal("0.20"), 100),
        ("quero uma bomba", None, None),
    ],
)
def test_extract_discount_cases(text: str, discount: Decimal | None, quantity: int | None) -> None:
    result_discount, result_quantity = extract_discount(text)
    assert result_discount == discount
    assert result_quantity == quantity


def test_extract_discount_ignores_bare_number_words() -> None:
    assert extract_discount("quero cinco bombas") == (None, None)


def test_extract_discount_handles_pecas_with_cedilla() -> None:
    assert extract_discount("faço 30 peças") == (None, 30)
