from pathlib import Path

import pytest

from revenueflow.services.checkout import is_explicit_confirmation

_ACCEPT = [
    "sim, pode fechar",
    "pode fechar",
    "Pode faturar!",
    "confirmo",
    "confirmo o pedido",
    "fechado",
    # Regression: real WhatsApp messages are punctuated in ways that used to
    # break the plain substring match ("sim... pode, fechar" never matched
    # "sim pode fechar" because the comma split the two halves) -- found
    # live, the checkout gate kept re-prompting for confirmation.
    "sim... pode, fechar!",
    "Ok, pode fechar.",
    "beleza, pode fechar!",
    # Regression: natural phrasings outside the original short list.
    "sim quero fechar",
    "quero fechar o pedido",
    "confirmado",
    "confirma o pedido",
    "pode confirmar",
    "fecha o pedido",
    "vamos fechar",
    "pode processar o pedido",
    "faz o pedido",
]
_REJECT = [
    "acho que sim",
    "talvez",
    "sim",
    "quanto fica o frete?",
    "quase isso, mas quero rever a quantidade",
    "nao, ainda estou pensando",
    "sim, mas quanto fica o frete?",
]


@pytest.mark.parametrize("text", _ACCEPT)
def test_accepts_unambiguous_close(text: str) -> None:
    assert is_explicit_confirmation(text) is True


@pytest.mark.parametrize("text", _REJECT)
def test_rejects_ambiguous_or_unrelated(text: str) -> None:
    assert is_explicit_confirmation(text) is False


def test_service_module_does_not_import_llm() -> None:
    source = Path(is_explicit_confirmation.__code__.co_filename).read_text(encoding="utf-8")
    assert "services.llm" not in source
    assert "import llm" not in source
