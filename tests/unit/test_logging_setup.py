import json
import logging

import pytest

from revenueflow.observability import logging_setup
from revenueflow.observability.logging_setup import JsonFormatter, configure_logging


def test_formatter_emits_parseable_json() -> None:
    record = logging.LogRecord(
        "revenueflow.test", logging.INFO, __file__, 1, "audit.turn", None, None
    )
    record.conversation_id = "c-1"
    record.cost_usd = 0.001

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "audit.turn"
    assert payload["severity"] == "INFO"
    assert payload["logger"] == "revenueflow.test"
    assert payload["conversation_id"] == "c-1"
    assert payload["cost_usd"] == pytest.approx(0.001)
    assert "timestamp" in payload


def test_formatter_serialises_unknown_types_via_str() -> None:
    record = logging.LogRecord("revenueflow.test", logging.INFO, __file__, 1, "x", None, None)
    record.weird = object()

    payload = json.loads(JsonFormatter().format(record))

    assert isinstance(payload["weird"], str)


def test_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("kaboom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "revenueflow.test", logging.ERROR, __file__, 1, "boom", None, sys.exc_info()
        )

    payload = json.loads(JsonFormatter().format(record))
    assert "kaboom" in payload["exc"]


@pytest.fixture
def _reset_root() -> object:
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    logging_setup._CONFIGURED = False
    yield
    root.handlers = saved
    root.setLevel(saved_level)
    logging_setup._CONFIGURED = False


def test_configure_logging_is_idempotent(_reset_root: object) -> None:
    configure_logging()
    configure_logging()

    root = logging.getLogger()
    json_handlers = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
    assert len(json_handlers) == 1


def test_configure_logging_flattens_extra(
    _reset_root: object, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    logging.getLogger("revenueflow.test").info("audit.turn", extra={"token_usage": 42})

    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "audit.turn"
    assert payload["token_usage"] == 42
