"""LLM_STUB baseline eval for intent classification.

This is a synthetic golden set scored against the deterministic keyword stub,
not a real-model evaluation. It stays in the CI suite to prove the stub path
(dev local + CI) has not regressed. The Vertex-backed golden set lives in
``tests/ai_eval/test_vertex_eval.py`` (marked ``live``, ADR-049).
"""

from revenueflow.domain.models import Intent
from revenueflow.services import classify

GOLDEN: list[tuple[str, Intent]] = [
    ("Bom dia, tudo bem?", Intent.GREETING),
    ("Ola, gostaria de uma informacao", Intent.GREETING),
    ("Qual o valor da bomba de 2cv?", Intent.PRICE_REQUEST),
    ("Quanto custa a instalacao?", Intent.PRICE_REQUEST),
    ("Voces tem essa bomba em estoque?", Intent.STOCK_REQUEST),
    ("Esse modelo esta disponivel para entrega?", Intent.STOCK_REQUEST),
    ("Pode me mandar um orcamento?", Intent.QUOTE_REQUEST),
    ("Preciso de uma cotacao para tres bombas", Intent.QUOTE_REQUEST),
    ("Quero comprar a bomba periferica agora", Intent.ORDER_REQUEST),
    ("Vou fazer pedido de duas unidades", Intent.ORDER_REQUEST),
    ("Cade meu pedido que fiz semana passada?", Intent.ORDER_STATUS),
    ("Quero cancelar a compra", Intent.CANCELLATION),
    ("Preciso falar com um atendente", Intent.HUMAN_SUPPORT),
    ("Procuro uma bomba para irrigacao", Intent.PRODUCT_SEARCH),
    ("Voce recomenda algum produto para poco?", Intent.PRODUCT_SEARCH),
]


async def test_intent_stub_accuracy_meets_baseline() -> None:
    hits = 0
    for phrase, expected in GOLDEN:
        intent, _ = await classify(phrase)
        if intent is expected:
            hits += 1
    accuracy = hits / len(GOLDEN)
    assert accuracy >= 0.8
