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

import logging
from typing import Any

from revenueflow.adapters import ChannelOutbound, get_outbound
from revenueflow.domain.models import Intent
from revenueflow.events import EventEnvelope
from revenueflow.observability import get_tracer, new_tracer, reset_tracer, set_tracer
from revenueflow.repositories import dispatch, processed_event
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import get_or_create, record_turn, resolve

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
    token = set_tracer(
        new_tracer(conversation_id=session.conversation_id, turn_id=envelope.event_id)
    )
    try:
        customer_id, lead_id = await resolve(phone)
        state_in: dict[str, Any] = {
            "conversation_id": session.conversation_id,
            "customer_text": text,
            "customer_id": customer_id,
            "lead_id": lead_id,
            "turn_id": envelope.event_id,
        }
        result = await get_graph().ainvoke(
            state_in, config={"configurable": {"thread_id": session.conversation_id}}
        )
        reply = str(result["reply"])
        await record_turn(session.conversation_id, intent=Intent(result["intent"]))

        dispatch_key = f"{session.conversation_id}:{envelope.event_id}"
        async with unit_of_work() as conn:
            reserved = await dispatch.reserve(conn, dispatch_key=dispatch_key)
        if reserved:
            await (outbound or get_outbound()).send(
                phone=phone, text=reply, dispatch_key=dispatch_key
            )

        get_tracer().end(outcome=str(result.get("final_outcome", "replied")))
        return True
    except Exception:
        _LOGGER.exception("process_event failed for %s", envelope.event_id)
        try:
            get_tracer().end(outcome="error")
        except Exception:
            _LOGGER.debug("tracer end after failure also failed", exc_info=True)
        raise
    finally:
        reset_tracer(token)
