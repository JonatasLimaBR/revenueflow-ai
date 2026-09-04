import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "***"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_PHONE = re.compile(r"\+?\d[\d()\s.-]{6,}\d")


def _mask_text(text: str, extra_terms: Sequence[str]) -> str:
    masked = _EMAIL.sub(REDACTED, text)
    masked = _CPF.sub(REDACTED, masked)
    masked = _PHONE.sub(REDACTED, masked)
    for term in extra_terms:
        if term:
            masked = re.sub(re.escape(term), REDACTED, masked, flags=re.IGNORECASE)
    return masked


def mask(value: Any, *, extra_terms: Sequence[str] = ()) -> Any:
    if isinstance(value, str):
        return _mask_text(value, extra_terms)
    if isinstance(value, Mapping):
        return {key: mask(item, extra_terms=extra_terms) for key, item in value.items()}
    if isinstance(value, list):
        return [mask(item, extra_terms=extra_terms) for item in value]
    if isinstance(value, tuple):
        return tuple(mask(item, extra_terms=extra_terms) for item in value)
    return value
