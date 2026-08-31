"""LLM_STUB baseline eval for price-ask extraction.

This is a synthetic golden set scored against the deterministic regex/word-map
extractor, not a real-model evaluation. It locks in the stub's behaviour and
will be replaced by a Gemini-backed golden set when that increment lands.
"""

from decimal import Decimal

from revenueflow.services.negotiation import extract_price_ask

DISCOUNT_GOLDEN: list[tuple[str, Decimal | None]] = [
    ("consegue 10% nesse?", Decimal("0.10")),
    ("da pra fazer 15% de desconto?", Decimal("0.15")),
    ("quero 20% off", Decimal("0.20")),
    ("aceita 5 por cento?", Decimal("0.05")),
    ("faz 30 por cento pra fechar?", Decimal("0.30")),
    ("dez por cento ja ajuda", Decimal("0.10")),
    ("vinte por cento e fecho agora", Decimal("0.20")),
    ("consigo 8% a vista?", Decimal("0.08")),
    ("preciso de 100 unidades", None),
    ("me ve 12 pecas", None),
    ("quero 3 caixas dessa bomba", None),
    ("consegue 15% em 50 unidades?", Decimal("0.15")),
    ("40 por cento em 200 pecas", Decimal("0.40")),
    ("bom dia, quero uma bomba d'agua", None),
    ("qual o prazo de entrega?", None),
]

TARGET_PRICE_GOLDEN: list[tuple[str, Decimal | None]] = [
    ("faz por R$ 1.200?", Decimal("1200")),
    ("consigo por 950?", Decimal("950")),
    ("fica em 1.500,00 reais?", Decimal("1500.00")),
    ("por 2000 fechamos", Decimal("2000")),
    ("aceita R$ 780,50?", Decimal("780.50")),
    ("me ve por 1.250", Decimal("1250")),
    ("fecha a 3.000 reais", Decimal("3000")),
    ("consegue baixar pra 899?", Decimal("899")),
    ("bom dia, tudo bem?", None),
    ("qual o prazo de entrega?", None),
]


def test_discount_extraction_stub_accuracy_meets_baseline() -> None:
    hits = sum(
        1 for text, discount in DISCOUNT_GOLDEN if extract_price_ask(text).discount == discount
    )
    accuracy = hits / len(DISCOUNT_GOLDEN)
    assert accuracy >= 0.8


def test_target_price_extraction_stub_accuracy_meets_baseline() -> None:
    hits = sum(
        1 for text, target in TARGET_PRICE_GOLDEN if extract_price_ask(text).target_price == target
    )
    accuracy = hits / len(TARGET_PRICE_GOLDEN)
    assert accuracy >= 0.8
