"""Active-sales campaign batch run (SPEC-022, ADR-019/020).

``run`` consumes ``opportunity(OPEN)`` rows created by the Opportunity Engine,
applies the deterministic Policy Gate (``policies.outbound_policy.evaluate``),
and sends a fixed template message through ``ChannelOutbound`` when allowed. It
never touches ``Opportunity.status`` or ``policies.opportunity_policy`` (the
Engine stays untouched) and never imports ``revenueflow.agents`` or
``services.llm`` — the first-contact message is a template, not a generation.

No database transaction spans the outbound HTTP call: every DB operation opens
its own short ``unit_of_work`` (the same discipline ``worker.consume._send_once``
already applies), so a slow or retried WhatsApp send never holds a pool
connection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.adapters import get_outbound
from revenueflow.config import get_settings
from revenueflow.domain.models import (
    CampaignContactStatus,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from revenueflow.observability import get_tracer, new_tracer, reset_tracer, set_tracer
from revenueflow.policies import outbound_policy
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import dispatch
from revenueflow.repositories import opportunity as opportunity_repo
from revenueflow.repositories import outbound_contact as contact_repo
from revenueflow.repositories.db import unit_of_work

_LOGGER = logging.getLogger(__name__)

_TEMPLATES: dict[OpportunityType, Callable[[Opportunity], str]] = {
    OpportunityType.REPLENISHMENT: lambda opp: (
        "Ola! Notamos que faz um tempo desde sua ultima compra"
        + (f" de {opp.product}" if opp.product else "")
        + ". Podemos ajudar com uma nova reposicao?"
    ),
    OpportunityType.QUOTE_RECOVERY: lambda opp: (
        "Ola! Sua proposta ainda esta disponivel. Posso ajudar a fechar?"
    ),
}


@dataclass(slots=True)
class CampaignResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    errors: int = 0


async def run(*, now: datetime | None = None) -> CampaignResult:
    settings = get_settings()
    moment = now or datetime.now(UTC)
    result = CampaignResult()
    token = set_tracer(
        new_tracer(conversation_id="campaign-run", turn_id=f"campaign-{uuid4().hex[:8]}")
    )
    try:
        async with unit_of_work() as conn:
            opportunities = await opportunity_repo.list_by_status(conn, OpportunityStatus.OPEN)

        for opp in opportunities:
            try:
                await _handle(opp, moment, settings.campaign_frequency_cap_days, result)
            except Exception:
                result.errors += 1
                get_tracer().event(
                    "campaign.candidate_failed", attrs={"opportunity_id": opp.opportunity_id}
                )
                _LOGGER.exception("campaign candidate failed: %s", opp.opportunity_id)

        get_tracer().event("campaign.done", attrs=asdict(result))
        get_tracer().end(outcome="ran")
        return result
    finally:
        await get_tracer().flush()
        reset_tracer(token)


async def _handle(
    opp: Opportunity, moment: datetime, frequency_cap_days: int, result: CampaignResult
) -> None:
    async with unit_of_work() as conn:
        customer = await customer_repo.get_by_id(conn, opp.customer_id)
    if customer is None:
        result.errors += 1
        _LOGGER.warning("campaign candidate has no customer: %s", opp.customer_id)
        return

    async with unit_of_work() as conn:
        last = await contact_repo.last_contact_at(conn, customer.customer_id)

    decision = outbound_policy.evaluate(
        has_opt_in=customer.consent_opt_in_at is not None,
        has_opt_out=customer.consent_opt_out_at is not None,
        last_contact_at=last,
        now=moment,
        frequency_cap_days=frequency_cap_days,
    )
    if not decision.allowed:
        async with unit_of_work() as conn:
            await contact_repo.record(
                conn,
                customer_id=customer.customer_id,
                opportunity_id=opp.opportunity_id,
                status=CampaignContactStatus.SKIPPED,
                skip_reason=decision.reason,
            )
        result.skipped += 1
        return

    dispatch_key = f"campaign:{opp.opportunity_id}:{moment.date().isoformat()}"
    async with unit_of_work() as conn:
        reserved = await dispatch.reserve(conn, dispatch_key=dispatch_key)
    if not reserved:
        return

    message = _TEMPLATES[opp.opportunity_type](opp)
    try:
        await get_outbound().send(phone=customer.phone, text=message, dispatch_key=dispatch_key)
    except Exception:
        async with unit_of_work() as conn:
            await contact_repo.record(
                conn,
                customer_id=customer.customer_id,
                opportunity_id=opp.opportunity_id,
                status=CampaignContactStatus.FAILED,
            )
        result.failed += 1
        raise

    async with unit_of_work() as conn:
        await contact_repo.record(
            conn,
            customer_id=customer.customer_id,
            opportunity_id=opp.opportunity_id,
            status=CampaignContactStatus.SENT,
        )
    result.sent += 1
