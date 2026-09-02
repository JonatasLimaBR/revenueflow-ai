from pathlib import Path

from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import fetchone, unit_of_work
from revenueflow.services import get_or_create, resolve

_KNOWN_PHONE = "5511900000001"
_KNOWN_CUSTOMER = "CUST-001"


async def test_resolve_is_stable_per_phone_and_isolated_across_phones(db: None) -> None:
    customer_id, lead_id = await resolve("+5511900000030")
    assert customer_id is None
    assert lead_id is not None

    customer_again, lead_again = await resolve("+5511900000030")
    assert customer_again is None
    assert lead_again == lead_id

    _, other_lead = await resolve("+5511900000031")
    assert other_lead is not None
    assert other_lead != lead_id


async def test_known_phone_resolves_to_customer_and_sets_session(db: None) -> None:
    session = await get_or_create(_KNOWN_PHONE)

    customer_id, lead_id = await resolve(_KNOWN_PHONE)
    assert customer_id == _KNOWN_CUSTOMER
    assert lead_id is None

    async with unit_of_work() as conn:
        await session_repo.set_customer(conn, session.conversation_id, customer_id)
        row = await fetchone(
            conn,
            "SELECT customer_id FROM conversation_session WHERE conversation_id = %s",
            (session.conversation_id,),
        )
    assert row is not None
    assert row["customer_id"] == _KNOWN_CUSTOMER


async def test_unknown_phone_creates_provisional_lead_only(db: None) -> None:
    phone = "5511911112222"

    customer_id, lead_id = await resolve(phone)
    assert customer_id is None
    assert lead_id is not None

    async with unit_of_work() as conn:
        assert await customer_repo.get_by_phone(conn, phone) is None
        stored_lead = await lead_repo.get_by_phone(conn, phone)
    assert stored_lead is not None
    assert stored_lead.lead_id == lead_id


async def test_known_customer_resolution_is_idempotent(db: None) -> None:
    async with unit_of_work() as conn:
        before = await fetchone(conn, "SELECT count(*) AS n FROM customer")

    first = await resolve(_KNOWN_PHONE)
    second = await resolve(_KNOWN_PHONE)
    assert first == second == (_KNOWN_CUSTOMER, None)

    async with unit_of_work() as conn:
        after = await fetchone(conn, "SELECT count(*) AS n FROM customer")
    assert before is not None and after is not None
    assert before["n"] == after["n"]


def test_identity_module_does_not_import_llm() -> None:
    source = Path("src/revenueflow/services/identity.py").read_text(encoding="utf-8")
    assert "services.llm" not in source
