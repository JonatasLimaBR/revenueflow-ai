from datetime import UTC, datetime
from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import (
    ConversationSession,
    Intent,
    Lead,
    LeadStatus,
    SessionStatus,
)
from revenueflow.repositories import (
    dispatch,
    processed_event,
    sim_catalog,
    sim_inventory,
    sim_sales,
)
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories import session as session_repo


async def test_processed_event_claim_is_idempotent(conn: AsyncConnection[Any]) -> None:
    assert await processed_event.claim(conn, kind="inbound", key="evt-1") is True
    assert await processed_event.claim(conn, kind="inbound", key="evt-1") is False
    assert await processed_event.claim(conn, kind="inbound", key="evt-2") is True


async def test_dispatch_reserve_is_idempotent(conn: AsyncConnection[Any]) -> None:
    assert await dispatch.reserve(conn, dispatch_key="d-1") is True
    assert await dispatch.reserve(conn, dispatch_key="d-1") is False
    assert await dispatch.reserve(conn, dispatch_key="d-2") is True


async def test_lead_create_and_get_by_phone(conn: AsyncConnection[Any]) -> None:
    lead = Lead(
        lead_id="lead-1",
        phone="+5511900000001",
        status=LeadStatus.NEW,
        created_at=datetime.now(UTC),
    )
    await lead_repo.create(conn, lead)

    fetched = await lead_repo.get_by_phone(conn, "+5511900000001")
    assert fetched is not None
    assert fetched.lead_id == "lead-1"
    assert fetched.status is LeadStatus.NEW

    duplicate = Lead(
        lead_id="lead-2",
        phone="+5511900000001",
        status=LeadStatus.QUALIFYING,
        created_at=datetime.now(UTC),
    )
    await lead_repo.create(conn, duplicate)

    still_first = await lead_repo.get_by_phone(conn, "+5511900000001")
    assert still_first is not None
    assert still_first.lead_id == "lead-1"


async def test_session_lifecycle(conn: AsyncConnection[Any]) -> None:
    session = ConversationSession(
        conversation_id="conv-1",
        phone="+5511900000002",
        status=SessionStatus.OPEN,
        last_interaction=datetime.now(UTC),
    )
    await session_repo.create(conn, session)

    found = await session_repo.get_open_by_phone(conn, "+5511900000002")
    assert found is not None
    assert found.conversation_id == "conv-1"
    assert found.status is SessionStatus.OPEN

    await session_repo.touch(conn, "conv-1", intent=Intent.PRODUCT_SEARCH, agent="router")
    touched = await session_repo.get_open_by_phone(conn, "+5511900000002")
    assert touched is not None
    assert touched.current_intent is Intent.PRODUCT_SEARCH
    assert touched.current_agent == "router"

    await session_repo.update_status(conn, "conv-1", SessionStatus.CLOSED)
    assert await session_repo.get_open_by_phone(conn, "+5511900000002") is None


async def test_sim_catalog_search_and_get(conn: AsyncConnection[Any]) -> None:
    results = await sim_catalog.search(conn, "1cv")
    assert len(results) >= 1

    product_id = results[0]["product_id"]
    row = await sim_catalog.get(conn, product_id)
    assert row is not None
    assert row["product_id"] == product_id

    assert await sim_catalog.get(conn, "PMP-DOES-NOT-EXIST") is None


async def test_sim_inventory_get_available(conn: AsyncConnection[Any]) -> None:
    in_stock = await sim_inventory.get_available(conn, "PMP-050-PER", 10)
    assert in_stock["fulfillable"] is True
    assert in_stock["available"] >= 10

    missing = await sim_inventory.get_available(conn, "PMP-UNKNOWN", 1)
    assert missing == {
        "product_id": "PMP-UNKNOWN",
        "available": 0,
        "fulfillable": False,
        "lead_time_days": None,
    }


async def test_sim_sales_context_for(conn: AsyncConnection[Any]) -> None:
    rows = await sim_sales.context_for(conn, "CUST-001")
    assert len(rows) >= 1
    assert {"product_id", "last_qty", "last_order_at"} <= rows[0].keys()
