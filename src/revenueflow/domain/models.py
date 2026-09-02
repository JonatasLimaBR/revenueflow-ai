from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class SessionStatus(StrEnum):
    OPEN = "OPEN"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    CLOSED = "CLOSED"


class LeadStatus(StrEnum):
    NEW = "NEW"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    WON = "WON"
    LOST = "LOST"


class Intent(StrEnum):
    GREETING = "greeting"
    PRODUCT_SEARCH = "product_search"
    RECOMMENDATION = "recommendation"
    STOCK_REQUEST = "stock_request"
    PRICE_REQUEST = "price_request"
    QUOTE_REQUEST = "quote_request"
    NEGOTIATION = "negotiation"
    ORDER_REQUEST = "order_request"
    ORDER_STATUS = "order_status"
    CANCELLATION = "cancellation"
    HUMAN_SUPPORT = "human_support"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class NormalizedEvent:
    event_id: str
    occurred_at: datetime
    phone: str
    message_id: str
    message_type: str
    message_text: str


@dataclass(slots=True)
class ConversationSession:
    conversation_id: str
    phone: str
    status: SessionStatus
    last_interaction: datetime
    current_intent: Intent | None = None
    current_agent: str | None = None
    customer_id: str | None = None
    lead_id: str | None = None


@dataclass(slots=True)
class Lead:
    lead_id: str
    phone: str
    status: LeadStatus
    created_at: datetime


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(slots=True)
class PriceQuote:
    product_id: str
    list_price: Decimal
    customer_price: Decimal
    unit_cost: Decimal
    maximum_discount: Decimal | None
    minimum_margin: Decimal
    valid_until: date


@dataclass(slots=True)
class MarginBreakdown:
    revenue: Decimal
    cost: Decimal
    gross_profit: Decimal
    margin: Decimal


class PolicyReason(StrEnum):
    MARGIN_BELOW_MINIMUM = "margin_below_minimum"
    DISCOUNT_OUT_OF_POLICY = "discount_out_of_policy"
    WITHIN_POLICY = "within_policy"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    max_allowed: Decimal
    resulting_margin: Decimal
    requires_approval: bool
    reason: PolicyReason


@dataclass(slots=True)
class Approval:
    approval_id: str
    conversation_id: str
    turn_id: str
    reason: str
    requested_discount: Decimal
    current_margin: Decimal
    resulting_margin: Decimal
    amount: Decimal
    customer_ref: str | None
    status: ApprovalStatus
    expires_at: datetime | None = None
    approved_discount: Decimal | None = None
    decided_at: datetime | None = None
