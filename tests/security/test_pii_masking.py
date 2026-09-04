import logging
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from revenueflow.adapters import FakeOutbound, reset_outbound, set_outbound
from revenueflow.agents import build_graph
from revenueflow.events import make_envelope
from revenueflow.observability.masking import REDACTED, mask
from revenueflow.repositories.db import fetchall, read_connection
from revenueflow.worker import process_event, set_graph

_CPF_DOTTED = "123.456.789-00"
_CPF_PLAIN = "12345678900"
_EMAIL = "cliente@example.com"
_PHONE = "+55 11 99999-9999"


def test_masks_cpf_email_phone_in_text() -> None:
    out = mask(f"cpf {_CPF_DOTTED}, tel {_PHONE}, email {_EMAIL}")
    assert _CPF_DOTTED not in out
    assert _EMAIL not in out
    assert "99999-9999" not in out
    assert REDACTED in out


def test_masks_cpf_without_punctuation() -> None:
    assert _CPF_PLAIN not in mask(f"meu cpf e {_CPF_PLAIN} ok")


def test_masks_recursively_in_dict_and_list() -> None:
    flat = str(mask({"a": {"b": [f"cpf {_CPF_DOTTED}", _EMAIL, _PHONE]}}))
    for raw in (_CPF_DOTTED, _EMAIL, "99999-9999"):
        assert raw not in flat


def test_extra_terms_mask_a_name() -> None:
    assert "Joao Silva" not in mask("Cliente Joao Silva pediu", extra_terms=["Joao Silva"])


async def test_real_turn_leaves_no_raw_phone_in_audit_or_logs(
    db: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    set_graph(build_graph(MemorySaver()))
    fake = FakeOutbound()
    token = set_outbound(fake)
    env = make_envelope(
        "message_received",
        {
            "phone": "+5511987654321",
            "message_text": "bom dia",
            "message_id": f"wamid.{uuid4().hex}",
        },
        trace_id=f"t-{uuid4().hex}",
    )
    try:
        assert await process_event(env, outbound=fake) is True
    finally:
        reset_outbound(token)

    async with read_connection() as conn:
        rows = await fetchall(
            conn,
            "SELECT events::text AS events FROM audit_event WHERE turn_id = %s",
            (env.event_id,),
        )
    blob = "".join(r["events"] for r in rows)
    assert "5511987654321" not in blob
    assert "987654321" not in blob
    assert "987654321" not in caplog.text
