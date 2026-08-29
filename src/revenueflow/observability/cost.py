"""Token-cost estimation for model generations.

The per-model rates in :data:`MODEL_PRICES` are placeholders pending
confirmation of official Vertex AI Gemini pricing through the ``gcp-cli`` MCP.
"""

from __future__ import annotations

from revenueflow.observability.tracer import Usage

MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}


def _rates(model: str) -> tuple[float, float]:
    exact = MODEL_PRICES.get(model)
    if exact is not None:
        return exact
    for name, rates in MODEL_PRICES.items():
        if model.startswith(name):
            return rates
    return (0.0, 0.0)


def cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = _rates(model)
    total = input_tokens / 1_000_000 * in_rate + output_tokens / 1_000_000 * out_rate
    return round(total, 6)


def cost_from_usage(model: str, usage: Usage) -> float:
    return cost_usd(
        model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
