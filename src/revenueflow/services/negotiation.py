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

# The unit-suffixed form ("50 unidades") is the unambiguous, always-tried-first
# case. Found live (2026-09-11): a customer almost never phrases quantity that
# way in practice -- "quero 10", "manda 10", or a bare "10" replying to "quantas
# você quer?" all fell through to `quantity=None`, silently defaulting to 1 un
# in `negotiation_node` while the customer thought they'd negotiated for 10.
# `_QUANTITY_VERB`/`_QUANTITY_BARE` cover those. The exclusion of a following
# `%`/"por cento"/"reais" (so "quero 15%" or "quero 100 reais" are never
# misread as a quantity of 15/100) is checked separately in `_quantity_match`,
# not as a regex lookahead on `\d{1,5}` -- a lookahead there let the engine
# backtrack the digit run itself (e.g. "quero 100 reais" matching "10" instead
# of failing on "100"), which produced a wrong quantity instead of correctly
# rejecting the match.
_QUANTITY_UNIT = re.compile(r"(\d{1,5})\s*(?:un|unidades|pe[çc]as|caixas)")
_QUANTITY_VERB = re.compile(
    r"(?:quero|preciso de|manda[r]?|leva[r]?|fecha[r]?|s[aã]o|vou levar)\s+(\d{1,5})"
)
_QUANTITY_VERB_EXCLUDE = re.compile(r"\s*(?:%|por\s*cento|reais?\b)")
_QUANTITY_BARE = re.compile(r"^\s*(\d{1,5})\s*[.!?]?\s*$")

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


def _quantity_match(lowered: str) -> re.Match[str] | None:
    unit_match = _QUANTITY_UNIT.search(lowered)
    if unit_match is not None:
        return unit_match
    verb_match = _QUANTITY_VERB.search(lowered)
    if verb_match is not None and _QUANTITY_VERB_EXCLUDE.match(lowered, verb_match.end(1)):
        verb_match = None
    return verb_match or _QUANTITY_BARE.match(lowered)


def extract_price_ask(text: str) -> PriceAsk:
    """Return the discount, absolute target price, and quantity found in ``text``."""

    lowered = text.casefold()

    discount = _discount_fraction(lowered)

    quantity_match = _quantity_match(lowered)
    quantity = int(quantity_match.group(1)) if quantity_match is not None else None
    quantity_span = quantity_match.span(1) if quantity_match is not None else None

    target_price = None if discount is not None else _target_price(lowered, quantity_span)

    return PriceAsk(discount=discount, target_price=target_price, quantity=quantity)
