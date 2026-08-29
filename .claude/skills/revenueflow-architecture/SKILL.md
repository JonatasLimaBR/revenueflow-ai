# RevenueFlow Architecture Skill

## Use when
A task touches more than one module or changes an architectural boundary.

## Architecture
```text
WhatsApp
  ↓
FastAPI / Cloud Run
  ↓
Sales Supervisor / LangGraph
  ├─ Recommendation Agent (read-only)
  ├─ Negotiation Agent (constrained)
  └─ Checkout Agent (write)
        ↓
     Policy Engine
        ↓
 Human interrupt when required

PostgreSQL = OLTP + checkpoints
BigQuery = analytics/revenue intelligence
Pub/Sub = events
Vertex AI/Gemini = language/reasoning
Langfuse = agent tracing
```

## Invariant
A change that contradicts an accepted ADR needs a new superseding ADR first.
