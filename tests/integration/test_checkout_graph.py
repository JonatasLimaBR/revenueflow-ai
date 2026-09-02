from decimal import Decimal
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from revenueflow.agents.graph import build_graph
from revenueflow.repositories.db import fetchall, fetchone, read_connection

_BUY = "quero comprar a bomba d'agua 1cv"
_BUY_BIG_DISCOUNT = "quero comprar a bomba 1cv com 40% de desconto"
_CONFIRM = "sim, pode fechar"


async def _invoke(compiled, conversation_id: str, text: str, resume=None):  # noqa: ANN001
    payload = (
        Command(resume=resume)
        if resume is not None
        else {
            "conversation_id": conversation_id,
            "customer_text": text,
            "turn_id": f"t-{uuid4().hex}",
        }
    )
    return await compiled.ainvoke(payload, config={"configurable": {"thread_id": conversation_id}})


async def test_order_request_creates_quote_then_confirmation_places_order(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-co-{uuid4().hex}"

    quote_turn = await _invoke(compiled, conversation_id, _BUY)
    assert quote_turn["final_outcome"] == "quoted"
    assert "sim, pode fechar" in quote_turn["reply"].lower()

    async with read_connection() as conn:
        quotes = await fetchall(
            conn,
            "SELECT quote_id, status, total FROM quote WHERE conversation_id = %s",
            (conversation_id,),
        )
    assert len(quotes) == 1
    assert quotes[0]["status"] == "SENT"
    assert Decimal(quotes[0]["total"]) > 0

    confirm_turn = await _invoke(compiled, conversation_id, _CONFIRM)
    assert confirm_turn["final_outcome"] == "ordered"
    assert "confirmado" in confirm_turn["reply"].lower()

    async with read_connection() as conn:
        order = await fetchone(
            conn, "SELECT status FROM sales_order WHERE quote_id = %s", (quotes[0]["quote_id"],)
        )
        payment = await fetchone(
            conn,
            "SELECT status FROM payment WHERE order_id = "
            "(SELECT order_id FROM sales_order WHERE quote_id = %s)",
            (quotes[0]["quote_id"],),
        )
        quote_now = await fetchone(
            conn, "SELECT status FROM quote WHERE quote_id = %s", (quotes[0]["quote_id"],)
        )
    assert order["status"] == "PAID"
    assert payment["status"] == "APPROVED"
    assert quote_now["status"] == "ACCEPTED"


async def test_ambiguous_reply_reprompts_and_keeps_one_quote(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-co-{uuid4().hex}"

    await _invoke(compiled, conversation_id, _BUY)
    reprompt = await _invoke(compiled, conversation_id, "acho que sim, mas me diz o frete")
    assert reprompt["final_outcome"] == "confirm_reprompt"

    async with read_connection() as conn:
        quotes = await fetchall(
            conn, "SELECT status FROM quote WHERE conversation_id = %s", (conversation_id,)
        )
    assert len(quotes) == 1
    assert quotes[0]["status"] == "SENT"


async def test_out_of_policy_discount_pauses_for_approval_before_quote(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-co-{uuid4().hex}"

    result = await _invoke(compiled, conversation_id, _BUY_BIG_DISCOUNT)
    assert "__interrupt__" in result

    async with read_connection() as conn:
        approvals = await fetchall(
            conn, "SELECT status FROM approval WHERE conversation_id = %s", (conversation_id,)
        )
        quotes = await fetchall(
            conn, "SELECT 1 FROM quote WHERE conversation_id = %s", (conversation_id,)
        )
    assert len(approvals) == 1
    assert approvals[0]["status"] == "PENDING"
    assert quotes == []

    resumed = await _invoke(
        compiled, conversation_id, "", resume={"decision": "approve", "discount_pct": None}
    )
    assert resumed["final_outcome"] == "quoted"
    async with read_connection() as conn:
        quotes = await fetchall(
            conn, "SELECT status FROM quote WHERE conversation_id = %s", (conversation_id,)
        )
    assert len(quotes) == 1
    assert quotes[0]["status"] == "SENT"
