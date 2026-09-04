from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from revenueflow.domain.models import CampaignDecision, CampaignSkipReason
from revenueflow.policies.outbound_policy import evaluate, is_opt_out

_NOW = datetime(2026, 9, 4, tzinfo=UTC)


def test_evaluate_opted_out_wins_over_everything() -> None:
    decision = evaluate(
        has_opt_in=True,
        has_opt_out=True,
        last_contact_at=None,
        now=_NOW,
        frequency_cap_days=14,
    )

    assert decision == CampaignDecision(False, CampaignSkipReason.OPTED_OUT)


def test_evaluate_no_consent_blocks() -> None:
    decision = evaluate(
        has_opt_in=False,
        has_opt_out=False,
        last_contact_at=None,
        now=_NOW,
        frequency_cap_days=14,
    )

    assert decision == CampaignDecision(False, CampaignSkipReason.NO_CONSENT)


@pytest.mark.parametrize(
    ("days_ago", "cap_days", "allowed"),
    [
        (5, 14, False),
        (13, 14, False),
        (14, 14, True),
        (15, 14, True),
    ],
)
def test_evaluate_frequency_cap(days_ago: int, cap_days: int, allowed: bool) -> None:
    decision = evaluate(
        has_opt_in=True,
        has_opt_out=False,
        last_contact_at=_NOW - timedelta(days=days_ago),
        now=_NOW,
        frequency_cap_days=cap_days,
    )

    assert decision.allowed is allowed
    if not allowed:
        assert decision.reason is CampaignSkipReason.FREQUENCY_CAPPED


def test_evaluate_allowed_when_opted_in_and_never_contacted() -> None:
    decision = evaluate(
        has_opt_in=True,
        has_opt_out=False,
        last_contact_at=None,
        now=_NOW,
        frequency_cap_days=14,
    )

    assert decision == CampaignDecision(True, None)


@pytest.mark.parametrize("text", ["PARAR", " Parar ", "parar.", "SAIR", "cancelar", "Descadastrar"])
def test_is_opt_out_matches_keyword_variants(text: str) -> None:
    assert is_opt_out(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Voce pode parar de me mandar boleto errado?",
        "quero sair mais cedo hoje",
        "nao quero cancelar meu pedido",
        "quero comprar uma bomba",
        "",
    ],
)
def test_is_opt_out_rejects_substring_and_unrelated_text(text: str) -> None:
    assert is_opt_out(text) is False


def test_outbound_policy_module_is_pure() -> None:
    source = Path("src/revenueflow/policies/outbound_policy.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.services" not in import_lines
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.adapters" not in import_lines
    assert "revenueflow.repositories" not in import_lines
