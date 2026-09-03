from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.agents import graph as graph_module
from revenueflow.agents.graph import build_graph
from revenueflow.domain.models import HandoffStatus, Intent
from revenueflow.repositories import handoff as handoff_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import fetchall, unit_of_work
from revenueflow.services import get_or_create


def _payload(conversation_id: str, text: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "customer_text": text,
        "turn_id": f"t-{uuid4().hex}",
    }


async def test_explicit_request_routes_to_handoff_and_persists(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _classify(_text: str) -> tuple[Intent, float]:
        return Intent.HUMAN_SUPPORT, 0.95

    monkeypatch.setattr(graph_module, "classify", _classify)
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        _payload(session.conversation_id, "quero falar com um atendente"),
        config={"configurable": {"thread_id": session.conversation_id}},
    )

    assert result["final_outcome"] == "handoff"
    assert result["handoff_reason"] == "explicit_request"
    assert "atendente humano" in result["reply"]

    async with unit_of_work() as conn:
        rows = await handoff_repo.list_by_status(conn, HandoffStatus.PENDING)
        session_now = await session_repo.get_open_by_phone(conn, session.phone)
    mine = [h for h in rows if h.conversation_id == session.conversation_id]
    assert len(mine) == 1
    assert set(mine[0].context) == {
        "conversation_summary",
        "customer",
        "intent",
        "products",
        "quote",
        "objections",
        "reason",
        "next_best_action",
    }
    assert session_now is not None and session_now.status.value == "HUMAN_HANDOFF"


async def test_low_confidence_routes_to_handoff(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _classify(_text: str) -> tuple[Intent, float]:
        return Intent.RECOMMENDATION, 0.4

    monkeypatch.setattr(graph_module, "classify", _classify)
    conversation_id = f"c-lc-{uuid4().hex}"
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        _payload(conversation_id, "hmm nao sei bem o que quero"),
        config={"configurable": {"thread_id": conversation_id}},
    )

    assert result["handoff_reason"] == "low_confidence"
    assert result["final_outcome"] == "handoff"


async def test_high_value_routes_to_handoff_before_quote(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _classify(_text: str) -> tuple[Intent, float]:
        return Intent.PRICE_REQUEST, 0.9

    async def _get_price(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "customer_price": "100000.00",
            "unit_cost": "40000.00",
            "valid_until": "2026-12-31T00:00:00+00:00",
        }

    monkeypatch.setattr(graph_module, "classify", _classify)
    monkeypatch.setattr("revenueflow.agents.negotiation.tools_pricing.get_price", _get_price)
    conversation_id = f"c-hv-{uuid4().hex}"
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        _payload(conversation_id, "qual o preco da bomba 1cv"),
        config={"configurable": {"thread_id": conversation_id}},
    )

    assert result["handoff_reason"] == "high_value_order"
    assert result["final_outcome"] == "handoff"
    async with unit_of_work() as conn:
        quotes = await fetchall(
            conn, "SELECT 1 FROM quote WHERE conversation_id = %s", (conversation_id,)
        )
    assert quotes == []


async def test_second_handoff_keeps_one_pending(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _classify(_text: str) -> tuple[Intent, float]:
        return Intent.HUMAN_SUPPORT, 0.95

    monkeypatch.setattr(graph_module, "classify", _classify)
    conversation_id = f"c-2h-{uuid4().hex}"
    compiled = build_graph(MemorySaver())

    for _ in range(2):
        await compiled.ainvoke(
            _payload(conversation_id, "atendente por favor"),
            config={"configurable": {"thread_id": conversation_id}},
        )

    async with unit_of_work() as conn:
        rows = await handoff_repo.list_by_status(conn, HandoffStatus.PENDING)
    assert len([h for h in rows if h.conversation_id == conversation_id]) == 1


async def test_handoff_survives_context_failure(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _classify(_text: str) -> tuple[Intent, float]:
        return Intent.HUMAN_SUPPORT, 0.95

    async def _boom(_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("context down")

    monkeypatch.setattr(graph_module, "classify", _classify)
    monkeypatch.setattr("revenueflow.agents.handoff.handoff_svc.build_context", _boom)
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        _payload(session.conversation_id, "atendente"),
        config={"configurable": {"thread_id": session.conversation_id}},
    )

    assert result["final_outcome"] == "handoff"
    async with unit_of_work() as conn:
        rows = await handoff_repo.list_by_status(conn, HandoffStatus.PENDING)
    mine = [h for h in rows if h.conversation_id == session.conversation_id]
    assert len(mine) == 1
    assert mine[0].context == {"reason": "explicit_request", "intent": "human_support"}
