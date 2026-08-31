"""LLM_STUB baseline eval for discount-and-quantity extraction.

This is a synthetic golden set scored against the deterministic regex/word-map
extractor, not a real-model evaluation. It locks in the stub's behaviour and
will be replaced by a Gemini-backed golden set when that increment lands.
"""

from decimal import Decimal

from revenueflow.services.negotiation import extract_discount

GOLDEN: list[tuple[str, Decimal | None, int | None]] = [
    ("consegue 10% nesse?", Decimal("0.10"), None),
    ("da pra fazer 15% de desconto?", Decimal("0.15"), None),
    ("quero 20% off", Decimal("0.20"), None),
    ("aceita 5 por cento?", Decimal("0.05"), None),
    ("faz 30 por cento pra fechar?", Decimal("0.30"), None),
    ("dez por cento ja ajuda", Decimal("0.10"), None),
    ("vinte por cento e fecho agora", Decimal("0.20"), None),
    ("consigo 8% a vista?", Decimal("0.08"), None),
    ("preciso de 100 unidades", None, 100),
    ("me ve 12 pecas", None, 12),
    ("quero 3 caixas dessa bomba", None, 3),
    ("consegue 15% em 50 unidades?", Decimal("0.15"), 50),
    ("40 por cento em 200 pecas", Decimal("0.40"), 200),
    ("bom dia, quero uma bomba d'agua", None, None),
    ("qual o prazo de entrega?", None, None),
]


def test_discount_extraction_stub_accuracy_meets_baseline() -> None:
    hits = sum(1 for text, discount, _ in GOLDEN if extract_discount(text)[0] == discount)
    accuracy = hits / len(GOLDEN)
    assert accuracy >= 0.8
