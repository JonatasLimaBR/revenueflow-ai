from revenueflow.services import resolve


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
