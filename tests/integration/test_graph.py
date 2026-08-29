import re
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from psycopg import AsyncConnection

from revenueflow.agents.graph import build_graph
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


async def test_migrate_created_checkpoint_table(conn: AsyncConnection[Any]) -> None:
    cur = await conn.execute("SELECT to_regclass('public.checkpoints')")
    row = await cur.fetchone()
    assert row is not None
    assert row[0] is not None
