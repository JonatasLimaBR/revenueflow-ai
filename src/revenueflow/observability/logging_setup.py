"""Structured JSON logging for Cloud Logging (SPEC-034).

Cloud Run captures stdout; a JSON line becomes ``jsonPayload.*``, which
``google_logging_metric`` can ``EXTRACT`` without brittle text regexes. The
formatter is stdlib only: it flattens ``extra=`` fields onto the top-level
object so ``_LOGGER.info("audit.turn", extra={...})`` is queryable per field.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from revenueflow.config import get_settings

_RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger. Idempotent."""

    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(get_settings().log_level.upper())
    _CONFIGURED = True
