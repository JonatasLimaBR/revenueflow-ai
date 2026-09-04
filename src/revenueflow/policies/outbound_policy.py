"""Active-contact Policy Gate (SPEC-022, ADR-020).

``evaluate`` is the whole gate: opt-out always wins, then explicit opt-in is
required, then a frequency cap on top of that — pure, no I/O, ``now`` injected
by the caller. ``is_opt_out`` is the companion guard for the inbound side: an
exact-match (not substring) keyword check, so it never misfires on a sentence
that merely contains one of the words.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta

from revenueflow.domain.models import CampaignDecision, CampaignSkipReason

OPT_OUT_KEYWORDS = frozenset({"parar", "sair", "cancelar", "descadastrar"})


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_opt_out(text: str) -> bool:
    """Return True only when ``text`` IS an opt-out keyword, not merely contains one."""

    normalized = _normalize(text).strip().rstrip(".!?")
    return normalized in OPT_OUT_KEYWORDS


def evaluate(
    *,
    has_opt_in: bool,
    has_opt_out: bool,
    last_contact_at: datetime | None,
    now: datetime,
    frequency_cap_days: int,
) -> CampaignDecision:
    """Policy Gate for active contact (ADR-020): opt-out > opt-in > frequency."""

    if has_opt_out:
        return CampaignDecision(False, CampaignSkipReason.OPTED_OUT)
    if not has_opt_in:
        return CampaignDecision(False, CampaignSkipReason.NO_CONSENT)
    if last_contact_at is not None and (now - last_contact_at) < timedelta(days=frequency_cap_days):
        return CampaignDecision(False, CampaignSkipReason.FREQUENCY_CAPPED)
    return CampaignDecision(True, None)
