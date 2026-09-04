"""Message consumer: turn a ``message_received`` envelope into a customer reply.

``process_event`` is the whole vertical slice past the webhook: it claims the
envelope once for exactly-once processing, resolves the session and identity,
runs the LangGraph turn, records the turn, and sends the reply through the
outbound channel with a dispatch-key dedup guard.

Error handling: any unexpected exception ends the trace with ``outcome="error"``
(best effort) and is re-raised. The subscriber that drives this function owns the
ack / nack decision, so this function must not swallow failures.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command

from revenueflow.adapters import ChannelOutbound, get_outbound
from revenueflow.config import get_settings
from revenueflow.domain.models import Intent, SessionStatus
from revenueflow.events import EventEnvelope
from revenueflow.observability import get_tracer, new_tracer, reset_tracer, set_tracer
from revenueflow.policies import outbound_policy
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories import dispatch, processed_event
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import execute, unit_of_work
from revenueflow.services import get_or_create, record_turn, resolve

_HELD_FOR_APPROVAL = (
    "Sua solicitacao anterior ainda esta em analise; retornamos assim que aprovada."
)

_HELD_FOR_HANDOFF = "Sua conversa esta com um atendente humano; ele responde em breve."

_SLOW_REPLY = (
    "Estamos com um volume alto agora e sua mensagem esta demorando mais que o normal. "
    "Ja retorno com a resposta."
)

_OPT_OUT_CONFIRMED = (
    "Voce nao recebera mais contatos de campanha. Para duvidas, siga escrevendo normalmente."
)

_LOGGER = logging.getLogger(__name__)

_graph: Any | None = None


def set_graph(graph: Any) -> None:
    """Register the compiled LangGraph turn graph the consumer will invoke."""

    global _graph
    _graph = graph


def get_graph() -> Any:
    """Return the registered compiled graph, or raise if it was never set."""

    if _graph is None:
        raise RuntimeError("turn graph not set; call set_graph first")
    return _graph


async def _send_once(
    conversation_id: str,
    event_id: str,
    phone: str,
    text: str,
    outbound: ChannelOutbound | None,
) -> None:
    """Send ``text`` through the outbound channel behind a dispatch-key dedup guard."""

    dispatch_key = f"{conversation_id}:{event_id}"
    async with unit_of_work() as conn:
        reserved = await dispatch.reserve(conn, dispatch_key=dispatch_key)
    if reserved:
        await (outbound or get_outbound()).send(phone=phone, text=text, dispatch_key=dispatch_key)


async def _reply_timeout(
    conversation_id: str,
    event_id: str,
    phone: str | None,
    outbound: ChannelOutbound | None,
) -> None:
    """Send the fixed slowness reply and end the trace with ``outcome="timeout"``."""

    if phone is not None:
        await _send_once(conversation_id, event_id, phone, _SLOW_REPLY, outbound)
    try:
        get_tracer().end(outcome="timeout")
    except Exception:
        _LOGGER.debug("tracer end after timeout also failed", exc_info=True)


async def process_event(
    envelope: EventEnvelope, *, outbound: ChannelOutbound | None = None
) -> bool:
    """Process one ``message_received`` envelope.

    Returns ``True`` when the turn ran, ``False`` when the envelope was already
    processed. Re-raises any unexpected error after ending the trace.
    """

    async with unit_of_work() as conn:
        claimed = await processed_event.claim(conn, kind="turn", key=envelope.event_id)
    if not claimed:
        return False

    phone = str(envelope.payload["phone"])
    text = str(envelope.payload["message_text"])
    session = await get_or_create(phone)
    if session.status == SessionStatus.HUMAN_HANDOFF:
        await _send_once(
            session.conversation_id, envelope.event_id, phone, _HELD_FOR_HANDOFF, outbound
        )
        return True
    token = set_tracer(
        new_tracer(conversation_id=session.conversation_id, turn_id=envelope.event_id)
    )
    config = {"configurable": {"thread_id": session.conversation_id}}
    try:
        snapshot = await get_graph().aget_state(config)
        if "await_approval" in (snapshot.next or ()):
            await _send_once(
                session.conversation_id, envelope.event_id, phone, _HELD_FOR_APPROVAL, outbound
            )
            get_tracer().end(outcome="held_for_approval")
            return True

        customer_id, lead_id = await resolve(phone)
        if customer_id is not None:
            async with unit_of_work() as conn:
                await session_repo.set_customer(conn, session.conversation_id, customer_id)

        if outbound_policy.is_opt_out(text):
            if customer_id is not None:
                async with unit_of_work() as conn:
                    await customer_repo.set_consent_opt_out(conn, customer_id, datetime.now(UTC))
            await _send_once(
                session.conversation_id, envelope.event_id, phone, _OPT_OUT_CONFIRMED, outbound
            )
            get_tracer().end(outcome="opted_out")
            return True

        state_in: dict[str, Any] = {
            "conversation_id": session.conversation_id,
            "customer_text": text,
            "customer_id": customer_id,
            "lead_id": lead_id,
            "turn_id": envelope.event_id,
        }
        result = await asyncio.wait_for(
            get_graph().ainvoke(state_in, config=config),
            timeout=get_settings().turn_budget_s,
        )
        reply = str(result["reply"])
        await record_turn(
            session.conversation_id,
            intent=Intent(result["intent"]),
            agent=result.get("current_agent"),
        )
        await _send_once(session.conversation_id, envelope.event_id, phone, reply, outbound)
        get_tracer().end(outcome=str(result.get("final_outcome", "replied")))
        return True
    except TimeoutError:
        _LOGGER.warning("turn budget exceeded for %s", envelope.event_id)
        await _reply_timeout(session.conversation_id, envelope.event_id, phone, outbound)
        return True
    except Exception:
        _LOGGER.exception("process_event failed for %s", envelope.event_id)
        try:
            get_tracer().end(outcome="error")
        except Exception:
            _LOGGER.debug("tracer end after failure also failed", exc_info=True)
        raise
    finally:
        await get_tracer().flush()
        reset_tracer(token)


async def process_approval_decided(
    envelope: EventEnvelope, *, outbound: ChannelOutbound | None = None
) -> bool:
    """Resume the paused turn for one ``approval_decided`` envelope.

    Claims the event, serializes on the conversation via a transactional advisory
    lock, resumes the graph with the decision, and sends the final reply once.
    """

    async with unit_of_work() as conn:
        claimed = await processed_event.claim(conn, kind="resume", key=envelope.event_id)
    if not claimed:
        return False

    conversation_id = str(envelope.payload["conversation_id"])
    token = set_tracer(new_tracer(conversation_id=conversation_id, turn_id=envelope.event_id))
    try:
        async with unit_of_work() as conn:
            await execute(conn, "SELECT pg_advisory_xact_lock(hashtext(%s))", (conversation_id,))
            result = await asyncio.wait_for(
                get_graph().ainvoke(
                    Command(
                        resume={
                            "decision": envelope.payload["decision"],
                            "discount_pct": envelope.payload.get("discount_pct"),
                        }
                    ),
                    config={"configurable": {"thread_id": conversation_id}},
                ),
                timeout=get_settings().turn_budget_s,
            )

        reply = str(result["reply"])
        intent = result.get("intent")
        await record_turn(
            conversation_id,
            intent=Intent(intent) if intent is not None else None,
            agent=result.get("current_agent"),
        )

        async with unit_of_work() as conn:
            phone = await session_repo.phone_for(conn, conversation_id)
        if phone is not None:
            await _send_once(conversation_id, envelope.event_id, phone, reply, outbound)

        get_tracer().end(outcome=str(result.get("final_outcome", "resumed")))
        return True
    except TimeoutError:
        _LOGGER.warning("resume turn budget exceeded for %s", envelope.event_id)
        async with unit_of_work() as conn:
            phone = await session_repo.phone_for(conn, conversation_id)
        await _reply_timeout(conversation_id, envelope.event_id, phone, outbound)
        return True
    except Exception:
        _LOGGER.exception("process_approval_decided failed for %s", envelope.event_id)
        try:
            get_tracer().end(outcome="error")
        except Exception:
            _LOGGER.debug("tracer end after failure also failed", exc_info=True)
        raise
    finally:
        await get_tracer().flush()
        reset_tracer(token)
