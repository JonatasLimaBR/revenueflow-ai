# Pub/Sub Skill

## Use when
Designing domain events or asynchronous processing.

## Event rules
Every event should include:
- event_id;
- event_type;
- occurred_at;
- trace_id;
- schema_version.

Consumers must be idempotent.

## RevenueFlow examples
- message_received
- lead_created
- quote_created
- opportunity_created
- approval_requested
- order_created

Never put secrets or unnecessary PII in events.
