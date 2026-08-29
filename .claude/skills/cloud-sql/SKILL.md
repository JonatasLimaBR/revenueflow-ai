# Cloud SQL PostgreSQL Skill

## Use when
Working on operational entities, migrations, indexes, transactions or persistence.

## System of record
PostgreSQL is the V1 operational source for:
- customers;
- leads;
- conversations;
- quotes;
- approvals;
- orders;
- agent checkpoints.

## Rules
- migrations are versioned;
- destructive migrations require explicit review;
- transactions protect order/approval invariants;
- connection pooling must be Cloud Run friendly;
- agents never query PostgreSQL directly; repositories/services mediate access.
