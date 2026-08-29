# Cloud Run Skill

## Use when
Building, inspecting or deploying RevenueFlow services on Cloud Run.

## Responsibilities
- validate container entrypoint;
- validate health endpoints;
- inspect service configuration;
- inspect logs;
- calculate env/secrets requirements;
- prepare deployment command;
- verify service account and IAM;
- review concurrency/min/max instances.

## Safety
Read operations are allowed.

A deployment must be explicitly requested by the user.
Deletion is never automatic.

Secrets must reference Secret Manager, not plaintext environment values.

## RevenueFlow defaults
Backend: FastAPI.
Region: environment-specific.
Runtime identity: dedicated service account.
Ingress/auth policy: defined by Terraform/ADR, never improvised.
