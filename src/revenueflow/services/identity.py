"""Identity resolution service.

:func:`resolve` matches the inbound phone against the ``customer`` store first
(exact match, deterministic): a known customer returns its real ``customer_id``
and no lead. An unknown phone falls back to get-or-create of a provisional lead
keyed by the exact phone number, so exactly one lead exists per phone and leads
stay isolated across customers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.domain.errors import DomainError
from revenueflow.domain.models import Lead, LeadStatus
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories.db import unit_of_work


async def resolve(phone: str) -> tuple[str | None, str | None]:
    """Return ``(customer_id, lead_id)`` for ``phone``.

    A known customer resolves to ``(customer_id, None)``; an unknown phone
    resolves to ``(None, lead_id)`` after get-or-create of a provisional lead.
    """

    async with unit_of_work() as conn:
        customer = await customer_repo.get_by_phone(conn, phone)
        if customer is not None:
            return customer.customer_id, None
        existing = await lead_repo.get_by_phone(conn, phone)
        if existing is not None:
            return None, existing.lead_id
        provisional = Lead(
            lead_id=uuid4().hex,
            phone=phone,
            status=LeadStatus.NEW,
            created_at=datetime.now(UTC),
        )
        await lead_repo.create(conn, provisional)
        stored = await lead_repo.get_by_phone(conn, phone)
        if stored is None:
            raise DomainError("lead missing immediately after create")
        return None, stored.lead_id
