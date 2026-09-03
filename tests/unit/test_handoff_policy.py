from decimal import Decimal
from pathlib import Path

import pytest

from revenueflow.domain.models import HandoffReason
from revenueflow.policies.handoff_policy import should_handoff

_MIN_CONF = 0.55
_THRESHOLD = Decimal("50000")


def _call(intent: str, confidence: float, total: Decimal | None) -> HandoffReason | None:
    return should_handoff(
        intent=intent,
        confidence=confidence,
        resolved_total=total,
        min_confidence=_MIN_CONF,
        high_value_threshold=_THRESHOLD,
    )


def test_explicit_request_wins_over_everything() -> None:
    assert _call("human_support", 0.95, Decimal("999999")) is HandoffReason.EXPLICIT_REQUEST


def test_high_value_beats_low_confidence() -> None:
    assert _call("price_request", 0.9, Decimal("60000")) is HandoffReason.HIGH_VALUE_ORDER


def test_high_value_ignored_when_total_is_none() -> None:
    assert _call("price_request", 0.9, None) is None


def test_low_confidence_fires_below_threshold() -> None:
    assert _call("recommendation", 0.3, None) is HandoffReason.LOW_CONFIDENCE


def test_no_handoff_when_confident_and_cheap() -> None:
    assert _call("recommendation", 0.8, Decimal("100")) is None


@pytest.mark.parametrize("confidence", [0.549, 0.0])
def test_low_confidence_boundary(confidence: float) -> None:
    assert _call("greeting", confidence, None) is HandoffReason.LOW_CONFIDENCE


def test_policy_module_is_pure() -> None:
    source = Path("src/revenueflow/policies/handoff_policy.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.services" not in import_lines
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.adapters" not in import_lines
    assert "revenueflow.repositories" not in import_lines
