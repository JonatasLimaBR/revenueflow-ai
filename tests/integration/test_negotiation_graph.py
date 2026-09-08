from decimal import Decimal
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from revenueflow.agents.graph import build_graph
from revenueflow.config import get_settings
from revenueflow.domain.models import Intent
from revenueflow.repositories.db import fetchall, fetchone, read_connection
from revenueflow.services import get_or_create, record_turn

_IN_POLICY = "qual o preço da bomba com 5% de desconto?"
_OUT_OF_POLICY = "qual o preço da bomba com 40% de desconto?"
_OUT_OF_POLICY_TARGET = "qual o preço da bomba? faz por R$ 1?"
_QTY_FOLLOWUP = "qual o preço da bomba para 3 unidades?"
_QUOTE_FOLLOWUP = "quero um orçamento"


async def test_in_policy_discount_is_proposed_without_approval(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-neg-in-{uuid4().hex}"
    turn_id = f"t-{uuid4().hex}"

    result = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _IN_POLICY,
            "turn_id": turn_id,
        },
        config={"configurable": {"thread_id": conversation_id}},
    )

    assert result["intent"] == Intent.PRICE_REQUEST.value
    assert result["final_outcome"] in {"proposed", "quoted"}
    assert "__interrupt__" not in result
    assert result["requested_quantity"] >= 1
    assert "checkout_discount" in result

    async with read_connection() as conn:
        row = await fetchone(
            conn,
            "SELECT approval_id FROM approval WHERE conversation_id = %s AND turn_id = %s",
            (conversation_id, turn_id),
        )
    assert row is None


async def test_out_of_policy_discount_opens_pending_approval(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-neg-out-{uuid4().hex}"
    turn_id = f"t-{uuid4().hex}"

    result = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _OUT_OF_POLICY,
            "turn_id": turn_id,
        },
        config={"configurable": {"thread_id": conversation_id}},
    )

    assert result["final_outcome"] == "pending_approval"
    assert "__interrupt__" in result
    assert "aprova" in result["reply"].lower()
    assert result["price_quote"]["customer_price"]
    assert result["requested_quantity"] >= 1
    assert result["requested_discount"]

    async with read_connection() as conn:
        rows = await fetchall(
            conn,
            "SELECT status, resulting_margin, expires_at FROM approval "
            "WHERE conversation_id = %s AND turn_id = %s",
            (conversation_id, turn_id),
        )
    assert len(rows) == 1
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["resulting_margin"] is not None
    assert rows[0]["expires_at"] is not None


async def test_out_of_policy_target_price_opens_pending_approval(db: None) -> None:
    compiled = build_graph(MemorySaver())
    conversation_id = f"c-neg-tgt-{uuid4().hex}"
    turn_id = f"t-{uuid4().hex}"

    result = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _OUT_OF_POLICY_TARGET,
            "turn_id": turn_id,
        },
        config={"configurable": {"thread_id": conversation_id}},
    )

    assert result["final_outcome"] == "pending_approval"
    assert "__interrupt__" in result

    async with read_connection() as conn:
        rows = await fetchall(
            conn,
            "SELECT status FROM approval WHERE conversation_id = %s AND turn_id = %s",
            (conversation_id, turn_id),
        )
    assert len(rows) == 1
    assert rows[0]["status"] == "PENDING"


async def test_negotiation_turn_records_current_agent_on_session(db: None) -> None:
    session = await get_or_create(f"5511{uuid4().hex[:9]}")
    conversation_id = session.conversation_id
    turn_id = f"t-{uuid4().hex}"

    compiled = build_graph(MemorySaver())
    result = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _IN_POLICY,
            "turn_id": turn_id,
        },
        config={"configurable": {"thread_id": conversation_id}},
    )
    await record_turn(
        conversation_id,
        intent=Intent(result["intent"]),
        agent=result.get("current_agent"),
    )

    async with read_connection() as conn:
        row = await fetchone(
            conn,
            "SELECT current_agent FROM conversation_session WHERE conversation_id = %s",
            (conversation_id,),
        )
    assert row is not None
    assert row["current_agent"] == "negotiation"


async def test_quantity_followup_reapplies_the_established_discount(db: None) -> None:
    """Regression: a follow-up that only changes quantity ("qual o preço para
    3 unidades?") never repeats the discount already negotiated. Found live:
    negotiation_node treated the missing discount as "no discount asked" and
    silently reset checkout_discount to 0 instead of re-proposing the same
    rate for the new quantity."""

    compiled = build_graph(MemorySaver())
    conversation_id = f"c-neg-qty-{uuid4().hex}"
    config = {"configurable": {"thread_id": conversation_id}}

    first = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _IN_POLICY,
            "turn_id": f"t-{uuid4().hex}",
        },
        config=config,
    )
    assert first["final_outcome"] == "proposed"
    established = Decimal(first["checkout_discount"])
    assert established > 0

    second = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _QTY_FOLLOWUP,
            "turn_id": f"t-{uuid4().hex}",
        },
        config=config,
    )

    assert second["requested_quantity"] == 3
    assert Decimal(second["checkout_discount"]) == established


async def test_closing_followup_keeps_the_established_quantity(db: None) -> None:
    """Regression: a follow-up that repeats neither the product nor the
    quantity ("quero um orçamento") never restates what a prior turn already
    established. Found live: negotiation_node defaulted the missing quantity
    to 1, silently dropping a 20-unit request back to a single unit right as
    the customer tried to confirm ("pode faturar")."""

    compiled = build_graph(MemorySaver())
    conversation_id = f"c-neg-qty-close-{uuid4().hex}"
    config = {"configurable": {"thread_id": conversation_id}}

    first = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _QTY_FOLLOWUP,
            "turn_id": f"t-{uuid4().hex}",
        },
        config=config,
    )
    assert first["requested_quantity"] == 3

    second = await compiled.ainvoke(
        {
            "conversation_id": conversation_id,
            "customer_text": _QUOTE_FOLLOWUP,
            "turn_id": f"t-{uuid4().hex}",
        },
        config=config,
    )

    assert second["requested_quantity"] == 3


async def test_paused_turn_persists_a_checkpoint(db: None) -> None:
    conversation_id = f"c-neg-ckpt-{uuid4().hex}"

    async with AsyncPostgresSaver.from_conn_string(get_settings().database_url) as saver:
        await saver.setup()
        compiled = build_graph(saver)
        result = await compiled.ainvoke(
            {
                "conversation_id": conversation_id,
                "customer_text": _OUT_OF_POLICY,
                "turn_id": f"t-{uuid4().hex}",
            },
            config={"configurable": {"thread_id": conversation_id}},
        )

    assert "__interrupt__" in result

    async with read_connection() as conn:
        row = await fetchone(
            conn,
            "SELECT count(*) AS n FROM checkpoints WHERE thread_id = %s",
            (conversation_id,),
        )
    assert row is not None
    assert row["n"] >= 1
