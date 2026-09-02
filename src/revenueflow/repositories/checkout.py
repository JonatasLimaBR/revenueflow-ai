from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from revenueflow.domain.models import Order, OrderStatus, Payment, Quote, QuoteStatus
from revenueflow.repositories.db import execute, fetchone

_INSERT_QUOTE = """
INSERT INTO quote (quote_id, conversation_id, customer_ref, items, total, expiration, status)
VALUES (%s, %s, %s, %s, %s, %s, 'SENT')
ON CONFLICT (conversation_id) WHERE status = 'SENT' DO NOTHING
"""
_GET_OPEN_QUOTE = """
SELECT quote_id, conversation_id, customer_ref, items, total, expiration, status
FROM quote WHERE conversation_id = %s AND status = 'SENT'
"""
_SET_QUOTE_STATUS = "UPDATE quote SET status = %s WHERE quote_id = %s"

_INSERT_ORDER = """
INSERT INTO sales_order (order_id, quote_id, customer_ref, items, total, status)
VALUES (%s, %s, %s, %s, %s, 'CONFIRMED')
ON CONFLICT (quote_id) DO NOTHING
"""
_GET_ORDER_BY_QUOTE = """
SELECT order_id, quote_id, customer_ref, items, total, status
FROM sales_order WHERE quote_id = %s
"""
_SET_ORDER_STATUS = "UPDATE sales_order SET status = %s WHERE order_id = %s"

_INSERT_PAYMENT = """
INSERT INTO payment (payment_id, order_id, amount, status)
VALUES (%s, %s, %s, %s)
"""


def _to_quote(row: dict[str, Any]) -> Quote:
    return Quote(
        quote_id=row["quote_id"],
        conversation_id=row["conversation_id"],
        customer_ref=row["customer_ref"],
        items=list(row["items"]),
        total=row["total"],
        expiration=row["expiration"],
        status=QuoteStatus(row["status"]),
    )


def _to_order(row: dict[str, Any]) -> Order:
    return Order(
        order_id=row["order_id"],
        quote_id=row["quote_id"],
        customer_ref=row["customer_ref"],
        items=list(row["items"]),
        total=row["total"],
        status=OrderStatus(row["status"]),
    )


async def create_quote(conn: AsyncConnection[Any], quote: Quote) -> Quote:
    await execute(
        conn,
        _INSERT_QUOTE,
        (
            quote.quote_id,
            quote.conversation_id,
            quote.customer_ref,
            Jsonb(quote.items),
            quote.total,
            quote.expiration,
        ),
    )
    row = await fetchone(conn, _GET_OPEN_QUOTE, (quote.conversation_id,))
    return _to_quote(row) if row is not None else quote


async def get_open_quote(conn: AsyncConnection[Any], conversation_id: str) -> Quote | None:
    row = await fetchone(conn, _GET_OPEN_QUOTE, (conversation_id,))
    return _to_quote(row) if row is not None else None


async def set_quote_status(conn: AsyncConnection[Any], quote_id: str, status: QuoteStatus) -> None:
    await execute(conn, _SET_QUOTE_STATUS, (status.value, quote_id))


async def create_order(conn: AsyncConnection[Any], order: Order) -> Order:
    await execute(
        conn,
        _INSERT_ORDER,
        (
            order.order_id,
            order.quote_id,
            order.customer_ref,
            Jsonb(order.items),
            order.total,
        ),
    )
    row = await fetchone(conn, _GET_ORDER_BY_QUOTE, (order.quote_id,))
    return _to_order(row) if row is not None else order


async def get_order_by_quote(conn: AsyncConnection[Any], quote_id: str) -> Order | None:
    row = await fetchone(conn, _GET_ORDER_BY_QUOTE, (quote_id,))
    return _to_order(row) if row is not None else None


async def create_payment(conn: AsyncConnection[Any], payment: Payment) -> None:
    await execute(
        conn,
        _INSERT_PAYMENT,
        (payment.payment_id, payment.order_id, payment.amount, payment.status.value),
    )


async def mark_paid(conn: AsyncConnection[Any], order_id: str, quote_id: str) -> None:
    await execute(conn, _SET_ORDER_STATUS, (OrderStatus.PAID.value, order_id))
    await execute(conn, _SET_QUOTE_STATUS, (QuoteStatus.ACCEPTED.value, quote_id))


__all__ = [
    "create_order",
    "create_payment",
    "create_quote",
    "get_open_quote",
    "get_order_by_quote",
    "mark_paid",
    "set_quote_status",
]
