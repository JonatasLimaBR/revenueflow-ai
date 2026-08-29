"""Identity resolution service.

This slice has no customer store, so every caller is anonymous from a CRM point
of view: :func:`resolve` always returns ``customer_id = None`` and instead
get-or-creates a provisional lead keyed by the exact phone number. Exactly one
lead exists per phone, and no identifier other than the phone passed in is ever
consulted, which keeps leads isolated across customers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.domain.errors import DomainError
from revenueflow.domain.models import Lead, LeadStatus
from revenueflow.repositories import lead as lead_repo
from revenueflow.repositories.db import unit_of_work


async def resolve(phone: str) -> tuple[str | None, str | None]:
    """Return ``(customer_id, lead_id)`` for ``phone``; ``customer_id`` is always None."""

    async with unit_of_work() as conn:
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
