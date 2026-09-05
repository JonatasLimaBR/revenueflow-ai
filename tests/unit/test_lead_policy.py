from pathlib import Path

import pytest

from revenueflow.domain.models import Intent, LeadStatus
from revenueflow.policies.lead_policy import advance


def test_ordered_outcome_always_wins_to_won() -> None:
    assert (
        advance(LeadStatus.NEW, intent=Intent.GREETING, final_outcome="ordered") is LeadStatus.WON
    )


def test_quoted_outcome_advances_to_proposal() -> None:
    assert (
        advance(LeadStatus.QUALIFIED, intent=Intent.ORDER_REQUEST, final_outcome="quoted")
        is LeadStatus.PROPOSAL
    )


@pytest.mark.parametrize("intent", [Intent.NEGOTIATION, Intent.QUOTE_REQUEST])
def test_negotiation_intents_advance_to_qualified(intent: Intent) -> None:
    assert advance(LeadStatus.NEW, intent=intent, final_outcome=None) is LeadStatus.QUALIFIED


@pytest.mark.parametrize(
    "intent",
    [Intent.PRODUCT_SEARCH, Intent.RECOMMENDATION, Intent.STOCK_REQUEST, Intent.PRICE_REQUEST],
)
def test_browsing_intents_advance_to_qualifying(intent: Intent) -> None:
    assert advance(LeadStatus.NEW, intent=intent, final_outcome=None) is LeadStatus.QUALIFYING


def test_unrelated_intent_does_not_change_status() -> None:
    assert (
        advance(LeadStatus.QUALIFYING, intent=Intent.GREETING, final_outcome=None)
        is LeadStatus.QUALIFYING
    )


def test_never_downgrades() -> None:
    assert (
        advance(LeadStatus.QUALIFIED, intent=Intent.GREETING, final_outcome=None)
        is LeadStatus.QUALIFIED
    )
    assert (
        advance(LeadStatus.PROPOSAL, intent=Intent.PRODUCT_SEARCH, final_outcome=None)
        is LeadStatus.PROPOSAL
    )


@pytest.mark.parametrize("terminal", [LeadStatus.WON, LeadStatus.LOST])
def test_terminal_statuses_never_move(terminal: LeadStatus) -> None:
    assert advance(terminal, intent=Intent.ORDER_REQUEST, final_outcome="ordered") is terminal
    assert advance(terminal, intent=Intent.NEGOTIATION, final_outcome=None) is terminal


def test_lead_policy_module_is_pure() -> None:
    source = Path("src/revenueflow/policies/lead_policy.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "import" in line
    )
    assert "revenueflow.services" not in import_lines
    assert "revenueflow.agents" not in import_lines
    assert "revenueflow.repositories" not in import_lines
