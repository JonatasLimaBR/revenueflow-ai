"""Gemini client wrapper with a deterministic stub path.

Following ADR-028 (simulate first), the real Vertex/GenAI call path is written
but gated behind ``get_settings().llm_stub`` (default on). While the stub is
enabled nothing from the optional ``llm`` extra is imported and the helpers
return deterministic, network-free results derived from keyword matching. The
real path lazily imports ``google.genai`` and raises :class:`LLMError` on any
failure.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from revenueflow.config import get_settings
from revenueflow.domain.errors import LLMError
from revenueflow.domain.models import Intent
from revenueflow.observability import Usage, cost_usd, get_tracer

_GREETING = ("bom dia", "boa tarde", "boa noite", "oi", "ola")
_PRICE = ("quanto custa", "quanto e", "preco", "valor")
_STOCK = ("tem essa bomba", "tem essa", "tem em", "disponivel", "estoque")
_QUOTE = ("orcamento", "cotacao")
_ORDER = ("quero comprar", "fazer pedido", "comprar")
_ORDER_STATUS = ("cade meu pedido", "status do pedido", "meu pedido")
_CANCEL = ("cancelar",)
_HUMAN = ("falar com alguem", "atendente", "humano", "pessoa")
_PRODUCT = ("preciso de", "quero uma", "recomenda", "procuro", "produto", "bomba")

_NAME_IN_JSON = re.compile(r'"name"\s*:\s*"([^"]+)"')


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _classify_keyword(text: str) -> Intent:
    normalized = _normalize(text)

    def has(terms: tuple[str, ...]) -> bool:
        return any(term in normalized for term in terms)

    if has(_GREETING):
        return Intent.GREETING
    if has(_PRICE):
        return Intent.PRICE_REQUEST
    if has(_STOCK):
        return Intent.STOCK_REQUEST
    if has(_QUOTE):
        return Intent.QUOTE_REQUEST
    if has(_ORDER):
        return Intent.ORDER_REQUEST
    if has(_ORDER_STATUS):
        return Intent.ORDER_STATUS
    if has(_CANCEL):
        return Intent.CANCELLATION
    if has(_HUMAN):
        return Intent.HUMAN_SUPPORT
    if has(_PRODUCT):
        return Intent.PRODUCT_SEARCH
    return Intent.UNKNOWN


def _product_names(user: str) -> list[str]:
    names: list[str] = []
    for match in _NAME_IN_JSON.finditer(user):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names


def _stub_json(user: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if isinstance(properties, Mapping) and "intent" in properties:
        intent = _classify_keyword(user)
        matched = intent is not Intent.UNKNOWN
        return {"intent": intent.value, "confidence": 0.6 if matched else 0.3}
    return {}


def _stub_text(user: str) -> str:
    names = _product_names(user)
    if names:
        return (
            f"Encontrei estas opcoes para voce: {', '.join(names)}. "
            "Posso confirmar detalhes com voce?"
        )
    return (
        "Nao encontrei uma opcao que atenda ao seu pedido agora; "
        "um atendente humano vai dar sequencia."
    )


def _usage_of(response: Any) -> Usage:
    meta = getattr(response, "usage_metadata", None)
    input_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def _record(generation: Any, *, model: str, output: str, response: Any) -> None:
    usage = _usage_of(response)
    generation.update(
        output=output,
        usage=usage,
        cost_usd=cost_usd(
            model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        ),
    )


async def gemini_json(
    *, system: str, user: str, schema: Mapping[str, Any], model: str
) -> dict[str, Any]:
    """Return a JSON object from Gemini, or a deterministic stub."""

    if get_settings().llm_stub:
        return _stub_json(user, schema)
    return await _gemini_json_real(system=system, user=user, schema=schema, model=model)


async def gemini_text(*, system: str, user: str, model: str) -> str:
    """Return a free-text answer from Gemini, or a deterministic stub."""

    if get_settings().llm_stub:
        return _stub_text(user)
    return await _gemini_text_real(system=system, user=user, model=model)


async def _gemini_json_real(
    *, system: str, user: str, schema: Mapping[str, Any], model: str
) -> dict[str, Any]:
    from google import genai

    tracer = get_tracer()
    try:
        client = genai.Client()
        with tracer.generation(
            "llm.json", model=model, prompt_version="real", input=user
        ) as generation:
            response = await client.aio.models.generate_content(
                model=model,
                contents=user,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": dict(schema),
                    "system_instruction": system,
                },
            )
            text = response.text or ""
            parsed = json.loads(text)
            _record(generation, model=model, output=text, response=response)
    except Exception as exc:
        raise LLMError("gemini json call failed") from exc
    if not isinstance(parsed, dict):
        raise LLMError("gemini json call returned a non-object")
    return {str(key): value for key, value in parsed.items()}


async def _gemini_text_real(*, system: str, user: str, model: str) -> str:
    from google import genai

    tracer = get_tracer()
    try:
        client = genai.Client()
        with tracer.generation(
            "llm.text", model=model, prompt_version="real", input=user
        ) as generation:
            response = await client.aio.models.generate_content(
                model=model,
                contents=user,
                config={"system_instruction": system},
            )
            text = response.text or ""
            _record(generation, model=model, output=text, response=response)
    except Exception as exc:
        raise LLMError("gemini text call failed") from exc
    return str(text)
