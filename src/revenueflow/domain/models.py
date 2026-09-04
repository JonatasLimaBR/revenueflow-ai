from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class SessionStatus(StrEnum):
    OPEN = "OPEN"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
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


class QuoteStatus(StrEnum):
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"


class OrderStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PAID = "PAID"
    FAILED = "FAILED"


class PaymentStatus(StrEnum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"


@dataclass(slots=True)
class Quote:
    quote_id: str
    conversation_id: str
    customer_ref: str | None
    items: list[dict[str, Any]]
    total: Decimal
    expiration: datetime
    status: QuoteStatus


@dataclass(slots=True)
class Order:
    order_id: str
    quote_id: str
    customer_ref: str | None
    items: list[dict[str, Any]]
    total: Decimal
    status: OrderStatus


@dataclass(slots=True)
class Payment:
    payment_id: str
    order_id: str
    amount: Decimal
    status: PaymentStatus


@dataclass(slots=True)
class Customer:
    customer_id: str
    phone: str
    name: str | None
    segment: str | None
    created_at: datetime
    consent_opt_in_at: datetime | None = None
    consent_opt_out_at: datetime | None = None


class OpportunityType(StrEnum):
    REPLENISHMENT = "REPLENISHMENT"
    QUOTE_RECOVERY = "QUOTE_RECOVERY"


class OpportunityStatus(StrEnum):
    OPEN = "OPEN"
    CONVERTED = "CONVERTED"
    DISMISSED = "DISMISSED"


@dataclass(slots=True)
class Opportunity:
    opportunity_id: str
    customer_id: str
    opportunity_type: OpportunityType
    product: str | None
    estimated_revenue: Decimal | None
    probability: Decimal | None
    reason: str
    evidence: dict[str, Any]
    recommended_action: str
    status: OpportunityStatus
    created_at: datetime


class HandoffReason(StrEnum):
    EXPLICIT_REQUEST = "explicit_request"
    LOW_CONFIDENCE = "low_confidence"
    HIGH_VALUE_ORDER = "high_value_order"
    INTENT = "intent"
    RESPOND = "respond"


class HandoffStatus(StrEnum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


@dataclass(slots=True)
class Handoff:
    handoff_id: str
    conversation_id: str
    reason: HandoffReason
    context: dict[str, Any]
    status: HandoffStatus
    created_at: datetime


class CampaignContactStatus(StrEnum):
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class CampaignSkipReason(StrEnum):
    NO_CONSENT = "no_consent"
    OPTED_OUT = "opted_out"
    FREQUENCY_CAPPED = "frequency_capped"


@dataclass(frozen=True, slots=True)
class CampaignDecision:
    allowed: bool
    reason: CampaignSkipReason | None = None


@dataclass(slots=True)
class OutboundContact:
    contact_id: str
    customer_id: str
    opportunity_id: str
    status: CampaignContactStatus
    skip_reason: CampaignSkipReason | None
    contacted_at: datetime


@dataclass(slots=True)
class AuditEvent:
    audit_id: str
    trace_id: str
    conversation_id: str
    turn_id: str
    agent: str | None
    model: str | None
    prompt_version: str | None
    outcome: str
    policy_decision: str | None
    handoff: bool
    tools: list[str]
    token_usage: int
    cost_usd: Decimal
    latency_ms: int | None
    events: list[dict[str, Any]]
    created_at: datetime | None = None
