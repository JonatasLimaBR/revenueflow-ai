"""Pure price-ask extraction for the Negotiation Agent (DESIGN §4.4).

No I/O and no model call: a customer sentence in Portuguese goes in, a
``PriceAsk`` comes out. The percent is read either from digits (``15%``,
``20 por cento``) or from a small number-word map; an absolute target price is
read from an ``R$`` prefix, a ``reais``/``real`` suffix, or a ``por <number>``
phrase; the quantity is read from a unit-suffixed number (``50 unidades``,
``100 pecas``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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

_PRICE_NUMBER = r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?"
_ABSOLUTE_PRICE = re.compile(
    rf"r\$\s*(?P<pre>{_PRICE_NUMBER})"
    rf"|(?P<mid>{_PRICE_NUMBER})\s*(?:reais|real)"
    rf"|por\s+(?P<post>{_PRICE_NUMBER})"
)

_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class PriceAsk:
    discount: Decimal | None = None
    target_price: Decimal | None = None
    quantity: int | None = None


def _discount_fraction(lowered: str) -> Decimal | None:
    digits = _PERCENT_DIGITS.search(lowered)
    if digits is not None:
        return Decimal(digits.group(1)) / _HUNDRED
    words = _PERCENT_WORDS.search(lowered)
    if words is not None:
        return Decimal(_NUMBER_WORDS[words.group(1)]) / _HUNDRED
    return None


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", "."))


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _target_price(lowered: str, quantity_span: tuple[int, int] | None) -> Decimal | None:
    for match in _ABSOLUTE_PRICE.finditer(lowered):
        if quantity_span is not None and _overlaps(match.span(), quantity_span):
            continue
        raw = match.group("pre") or match.group("mid") or match.group("post")
        return _to_decimal(raw)
    return None


def extract_price_ask(text: str) -> PriceAsk:
    """Return the discount, absolute target price, and quantity found in ``text``."""

    lowered = text.casefold()

    discount = _discount_fraction(lowered)

    quantity_match = _QUANTITY.search(lowered)
    quantity = int(quantity_match.group(1)) if quantity_match is not None else None
    quantity_span = quantity_match.span() if quantity_match is not None else None

    target_price = None if discount is not None else _target_price(lowered, quantity_span)

    return PriceAsk(discount=discount, target_price=target_price, quantity=quantity)
