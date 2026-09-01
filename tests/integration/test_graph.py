import re
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from psycopg import AsyncConnection

from revenueflow.agents.graph import build_graph
from revenueflow.domain.errors import LLMError
from revenueflow.domain.models import Intent

_PRICE = re.compile(r"\d+[.,]\d{2}")


async def test_product_search_turn_is_grounded(db: None) -> None:
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        {"conversation_id": "c-test", "customer_text": "quero uma bomba d'agua 1cv"},
        config={"configurable": {"thread_id": "c-test"}},
    )

    assert result["intent"] == Intent.PRODUCT_SEARCH.value

    tool_results = result["tool_results"]
    assert tool_results
    search_entries = [e for e in tool_results if e["tool"] == "search_products"]
    assert search_entries
    names = [product["name"] for product in search_entries[0]["result"]]
    target = next(name for name in names if "1CV" in name)

    reply = result["reply"]
    assert isinstance(reply, str)
    assert reply
    assert target in reply
    assert "R$" not in reply
    assert _PRICE.search(reply) is None


async def test_greeting_turn_skips_recommendation(db: None) -> None:
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        {"conversation_id": "c-greet", "customer_text": "oi, tudo bem?"},
        config={"configurable": {"thread_id": "c-greet"}},
    )

    assert result["intent"] == Intent.GREETING.value
    assert result.get("tool_results", []) == []
    reply = result["reply"]
    assert isinstance(reply, str)
    assert reply


async def test_llmerror_in_classify_routes_to_handoff(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(_text: str) -> tuple[Intent, float]:
        raise LLMError("vertex unavailable")

    monkeypatch.setattr("revenueflow.agents.graph.classify", boom)
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        {"conversation_id": "c-hoff1", "customer_text": "quero uma bomba d'agua 1cv"},
        config={"configurable": {"thread_id": "c-hoff1"}},
    )

    assert result["handoff"] is True
    assert result["handoff_reason"] == "intent"
    assert result["final_outcome"] == "handoff"
    assert "atendente humano" in result["reply"]


async def test_llmerror_in_respond_routes_to_handoff(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(**_kwargs: Any) -> str:
        raise LLMError("vertex unavailable")

    monkeypatch.setattr("revenueflow.agents.graph.generate", boom)
    compiled = build_graph(MemorySaver())

    result = await compiled.ainvoke(
        {"conversation_id": "c-hoff2", "customer_text": "oi, tudo bem?"},
        config={"configurable": {"thread_id": "c-hoff2"}},
    )

    assert result["handoff"] is True
    assert result["handoff_reason"] == "respond"
    assert result["final_outcome"] == "handoff"
    assert "atendente humano" in result["reply"]


async def test_migrate_created_checkpoint_table(conn: AsyncConnection[Any]) -> None:
    cur = await conn.execute("SELECT to_regclass('public.checkpoints')")
    row = await cur.fetchone()
    assert row is not None
    assert row[0] is not None
