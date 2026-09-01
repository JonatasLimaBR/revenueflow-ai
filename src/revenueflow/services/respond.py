"""Customer-facing response generation service.

The reply is grounded only in ``tool_results``: those rows are serialized into a
delimited data block and handed to the model as DATA. When there are no results
the service returns a fixed Portuguese hand-off sentence without calling the
model at all.
"""

from __future__ import annotations

import json
from typing import Any

from revenueflow.config import get_settings
from revenueflow.domain.models import Intent
from revenueflow.observability import get_tracer
from revenueflow.services import llm
from revenueflow.services.prompts import PROMPTS

_NO_RESULTS = (
    "Ainda nao localizei essa informacao por aqui; "
    "um atendente humano vai dar sequencia ao seu atendimento."
)


async def generate(
    *,
    intent: Intent,
    customer_text: str,
    tool_results: list[dict[str, Any]],
) -> str:
    """Draft a reply grounded only in ``tool_results``."""

    if not tool_results:
        return _NO_RESULTS
    prompt = PROMPTS["respond"]
    model = get_settings().gemini_model
    data_block = json.dumps(tool_results, ensure_ascii=False, separators=(",", ":"))
    user = (
        f"Intencao detectada: {intent.value}\n"
        f"<mensagem_cliente>\n{customer_text}\n</mensagem_cliente>\n"
        f"<resultados>\n{data_block}\n</resultados>"
    )
    with get_tracer().generation("respond", model=model, prompt_version=prompt.version):
        return await llm.gemini_text(system=prompt.system, user=user, model=model)
