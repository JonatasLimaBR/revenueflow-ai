from datetime import UTC, datetime

from revenueflow.domain import (
    ConversationSession,
    Intent,
    Lead,
    LeadStatus,
    NormalizedEvent,
    SessionStatus,
)


def test_intent_enum_matches_spec_005_vocabulary() -> None:
    assert {i.value for i in Intent} == {
        "greeting",
        "product_search",
        "recommendation",
        "stock_request",
        "price_request",
        "quote_request",
        "negotiation",
        "order_request",
        "order_status",
        "cancellation",
        "human_support",
        "unknown",
    }


def test_session_status_is_the_slice_subset() -> None:
    assert {s.value for s in SessionStatus} == {
        "OPEN",
        "WAITING_CUSTOMER",
        "HUMAN_HANDOFF",
        "CLOSED",
    }


def test_lead_status_matches_spec_004_vocabulary() -> None:
    assert {s.value for s in LeadStatus} == {
        "NEW",
        "QUALIFYING",
        "QUALIFIED",
        "PROPOSAL",
        "WON",
        "LOST",
    }


def test_conversation_session_defaults_are_none() -> None:
    session = ConversationSession(
        conversation_id="c1",
        phone="+5511999999999",
        status=SessionStatus.OPEN,
        last_interaction=datetime(2026, 8, 29, tzinfo=UTC),
    )
    assert session.current_intent is None
    assert session.current_agent is None
    assert session.customer_id is None
    assert session.lead_id is None


def test_normalized_event_and_lead_are_constructible() -> None:
    event = NormalizedEvent(
        event_id="e1",
        occurred_at=datetime(2026, 8, 29, tzinfo=UTC),
        phone="+5511999999999",
        message_id="wamid.1",
        message_type="text",
        message_text="quero uma bomba d'agua",
    )
    lead = Lead(
        lead_id="l1",
        phone=event.phone,
        status=LeadStatus.NEW,
        created_at=event.occurred_at,
    )
    assert event.message_id == "wamid.1"
    assert lead.status is LeadStatus.NEW
