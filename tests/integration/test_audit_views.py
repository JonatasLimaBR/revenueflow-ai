from uuid import uuid4

from revenueflow.repositories.db import execute, fetchall, fetchone, unit_of_work

_INSERT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, NULL, NULL, NULL, %s, 'n/a', false,
    '[]'::jsonb, %s, %s, %s, '[]'::jsonb)
"""


async def test_cost_per_conversation_and_outcome(db: None) -> None:
    conv_a = f"c-{uuid4().hex}"
    conv_b = f"c-{uuid4().hex}"
    rows = [
        (conv_a, "replied", 100, "0.0010", 50),
        (conv_a, "replied", 200, "0.0020", 70),
        (conv_a, "handoff", 0, "0", 30),
        (conv_b, "quoted", 300, "0.0030", 90),
        (conv_b, "quoted", 100, "0.0010", 40),
    ]
    async with unit_of_work() as conn:
        for i, (conv, outcome, tokens, cost, latency) in enumerate(rows):
            aid = f"{conv}-{i}-{uuid4().hex[:6]}"
            await execute(
                conn, _INSERT, (aid, f"tr-{i}", conv, aid, outcome, tokens, cost, latency)
            )

        per_conv = await fetchall(
            conn,
            "SELECT conversation_id, cost_usd, tokens, turns FROM v_ai_cost_per_conversation "
            "WHERE conversation_id IN (%s, %s) ORDER BY conversation_id",
            (conv_a, conv_b),
        )
        per_a = await fetchone(
            conn,
            "SELECT * FROM v_ai_cost_per_conversation WHERE conversation_id = %s",
            (conv_a,),
        )

    by_id = {r["conversation_id"]: r for r in per_conv}
    assert by_id[conv_a]["turns"] == 3
    assert by_id[conv_a]["tokens"] == 300
    assert by_id[conv_b]["turns"] == 2
    assert per_a is not None
