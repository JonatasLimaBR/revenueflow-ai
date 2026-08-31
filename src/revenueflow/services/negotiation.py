"""Pure discount-and-quantity extraction for the Negotiation Agent (DESIGN §4.4).

No I/O and no model call: a customer sentence in Portuguese goes in, a
``(discount_fraction, quantity)`` pair comes out. The percent is read either from
digits (``15%``, ``20 por cento``) or from a small number-word map; the quantity
is read from a unit-suffixed number (``50 unidades``, ``100 pecas``).
"""

from __future__ import annotations

import re
from decimal import Decimal

_NUMBER_WORDS: dict[str, int] = {
    "cinco": 5,
    "dez": 10,
    "quinze": 15,
    "vinte": 20,
    "trinta": 30,
}

_PERCENT_DIGITS = re.compile(r"(\d{1,2})\s*(?:%|por\s*cento)")
_PERCENT_WORDS = re.compile(r"\b(cinco|dez|quinze|vinte|trinta)\s*(?:%|por\s*cento)")
_QUANTITY = re.compile(r"(\d{1,5})\s*(?:un|unidades|pe[çc]as|caixas)")

_HUNDRED = Decimal("100")


def extract_discount(text: str) -> tuple[Decimal | None, int | None]:
    """Return the requested discount fraction and quantity found in ``text``."""

    lowered = text.casefold()

    discount: Decimal | None = None
    digits = _PERCENT_DIGITS.search(lowered)
    if digits is not None:
        discount = Decimal(digits.group(1)) / _HUNDRED
    else:
        words = _PERCENT_WORDS.search(lowered)
        if words is not None:
            discount = Decimal(_NUMBER_WORDS[words.group(1)]) / _HUNDRED

    quantity_match = _QUANTITY.search(lowered)
    quantity = int(quantity_match.group(1)) if quantity_match is not None else None

    return discount, quantity
