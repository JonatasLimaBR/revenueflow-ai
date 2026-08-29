import pytest

from revenueflow.observability import cost_usd


def test_full_million_input_tokens() -> None:
    assert cost_usd("gemini-2.0-flash", input_tokens=1_000_000, output_tokens=0) == 0.10


def test_mixed_input_and_output() -> None:
    assert cost_usd(
        "gemini-2.0-flash", input_tokens=500_000, output_tokens=250_000
    ) == pytest.approx(0.05 + 0.10)


def test_unknown_model_is_free() -> None:
    assert cost_usd("mystery-model", input_tokens=1_000_000, output_tokens=1_000_000) == 0.0


def test_dated_variant_prefix_match() -> None:
    assert cost_usd("gemini-2.0-flash-001", input_tokens=1_000_000, output_tokens=0) == 0.10
