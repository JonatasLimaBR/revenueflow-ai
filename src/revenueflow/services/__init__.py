"""Application service layer for the WhatsApp inbound flow.

These callables orchestrate the repositories, the event publisher, the tracer,
and the (stubbed) Gemini client. They own no HTTP or transport concerns.
"""

from revenueflow.services.identity import resolve
from revenueflow.services.ingest import ingest_message
from revenueflow.services.intent import classify
from revenueflow.services.llm import gemini_json, gemini_text
from revenueflow.services.negotiation import extract_discount
from revenueflow.services.prompts import PROMPTS, Prompt
from revenueflow.services.respond import generate
from revenueflow.services.session import (
    close,
    get_or_create,
    mark_waiting_customer,
    record_turn,
)

__all__ = [
    "PROMPTS",
    "Prompt",
    "classify",
    "close",
    "extract_discount",
    "gemini_json",
    "gemini_text",
    "generate",
    "get_or_create",
    "ingest_message",
    "mark_waiting_customer",
    "record_turn",
    "resolve",
]
