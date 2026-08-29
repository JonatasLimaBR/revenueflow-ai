from revenueflow.domain.models import Intent
from revenueflow.services import close, get_or_create, record_turn


async def test_session_service_reuses_then_recreates_after_close(db: None) -> None:
    phone = "+5511900000020"

    first = await get_or_create(phone)
    again = await get_or_create(phone)
    assert again.conversation_id == first.conversation_id

    await close(first.conversation_id)

    after_close = await get_or_create(phone)
    assert after_close.conversation_id != first.conversation_id

    await record_turn(after_close.conversation_id, intent=Intent.PRODUCT_SEARCH)
