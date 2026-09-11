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


@pytest.mark.parametrize(
    "text",
    [
        "quero 10",
        "quero 10 bombas",
        "manda 10",
        "preciso de 10",
        "são 10",
        "10",
        "10.",
        "10?",
    ],
)
def test_extract_price_ask_reads_quantity_without_a_unit_word(text: str) -> None:
    # Found live (2026-09-11): a customer negotiating quantity almost never
    # says "10 unidades" -- "quero 10", "manda 10", or a bare "10" replying to
    # "quantas você quer?" all silently fell through to quantity=None, and
    # negotiation_node defaulted to 1 un instead of what the customer asked
    # for.
    assert extract_price_ask(text).quantity == 10


def test_extract_price_ask_quantity_verb_form_does_not_swallow_a_discount() -> None:
    # Regression for the fix above: `\d{1,5}` right after "quero" backtracked
    # past a `(?!...)` lookahead that tried to exclude a trailing "%"/"reais",
    # so "quero 100 reais" matched quantity=10 (from "10" of "100") instead of
    # correctly finding no quantity at all.
    assert extract_price_ask("quero 15%") == PriceAsk(discount=Decimal("0.15"))
    assert extract_price_ask("quero 100 reais") == PriceAsk(target_price=Decimal("100"))
