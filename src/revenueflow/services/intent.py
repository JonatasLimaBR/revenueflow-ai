"""Intent classification service.

Wraps :func:`revenueflow.services.llm.gemini_json` with the controlled-enum JSON
schema and coerces whatever comes back into a ``(Intent, confidence)`` pair that
is always valid: an unknown enum value falls back to ``Intent.UNKNOWN`` and the
confidence is clamped to ``[0, 1]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from revenueflow.config import get_settings
from revenueflow.domain.models import Intent
from revenueflow.observability import get_tracer
from revenueflow.services import llm
from revenueflow.services.prompts import PROMPTS

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": [i.value for i in Intent]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intent", "confidence"],
}


def _coerce(data: Mapping[str, Any]) -> tuple[Intent, float]:
    try:
        intent = Intent(str(data.get("intent", Intent.UNKNOWN.value)))
    except ValueError:
        intent = Intent.UNKNOWN
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return intent, max(0.0, min(1.0, confidence))


async def classify(text: str) -> tuple[Intent, float]:
    """Classify ``text`` into a controlled intent with a 0..1 confidence."""

    prompt = PROMPTS["intent"]
    model = get_settings().gemini_model
    user = f"<mensagem_cliente>\n{text}\n</mensagem_cliente>"
    with get_tracer().generation("intent", model=model, prompt_version=prompt.version):
        data = await llm.gemini_json(system=prompt.system, user=user, schema=_SCHEMA, model=model)
    return _coerce(data)
