import pytest

from revenueflow.domain.models import Intent
from revenueflow.services import classify

_CASES: list[tuple[str, Intent]] = [
    ("Bom dia!", Intent.GREETING),
    ("oi, tudo bem?", Intent.GREETING),
    ("qual o preco da bomba de 1cv?", Intent.PRICE_REQUEST),
    ("quanto custa esse modelo?", Intent.PRICE_REQUEST),
    ("tem essa bomba em estoque?", Intent.STOCK_REQUEST),
    ("o produto esta disponivel?", Intent.STOCK_REQUEST),
    ("preciso de um orcamento", Intent.QUOTE_REQUEST),
    ("me manda a cotacao", Intent.QUOTE_REQUEST),
    ("quero comprar uma bomba periferica", Intent.ORDER_REQUEST),
    ("gostaria de fazer pedido", Intent.ORDER_REQUEST),
    ("cade meu pedido?", Intent.ORDER_STATUS),
    ("qual o status do pedido?", Intent.ORDER_STATUS),
    ("quero cancelar", Intent.CANCELLATION),
    ("quero falar com um atendente", Intent.HUMAN_SUPPORT),
    ("pode me transferir para uma pessoa?", Intent.HUMAN_SUPPORT),
    ("procuro uma bomba para poco artesiano", Intent.PRODUCT_SEARCH),
    ("recomenda um produto para minha caixa", Intent.PRODUCT_SEARCH),
    ("xpto zzz nada disso", Intent.UNKNOWN),
]


@pytest.mark.parametrize(("phrase", "expected"), _CASES)
async def test_classify_covers_keyword_branches(phrase: str, expected: Intent) -> None:
    intent, confidence = await classify(phrase)
    assert intent is expected
    assert 0.0 <= confidence <= 1.0
    assert intent in set(Intent)
