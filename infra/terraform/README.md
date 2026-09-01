# infra/terraform

Provisions the RevenueFlow environment on GCP. Full procedure: `docs/engineering/deploy.md`.

## File layout

| File | Owns |
|---|---|
| `versions.tf` | providers (`google`, `random`), `data.google_project` |
| `backend.tf` | GCS remote state (partial config — pass `-backend-config` at init) |
| `variables.tf` / `terraform.tfvars.example` | inputs |
| `apis.tf` | `google_project_service` for every API used |
| `iam.tf` | runtime service account + project-scoped roles |
| `pubsub.tf` | topic + DLQ + pull subscription `revenueflow.messages`, resource-scoped IAM |
| `cloud_sql.tf` | Postgres 16 instance + db + `random_password` + user |
| `secrets.tf` | 6 app secrets (values added manually) + `db-password` + `database-url` (Terraform-versioned) |
| `cloud_run.tf` | the v2 service (env + secret refs + Cloud SQL volume) + public invoker |
| `budget.tf` | optional monthly budget alert |
| `outputs.tf` | service URL, connection name, topic/subscription ids, SA email |

The `revenueflow` Artifact Registry repo is **not** here — `bootstrap/` creates it, because
the CD pipeline pushes the image before this config's `apply` runs.

## Init / plan (human)

```bash
terraform init \
  -backend-config="bucket=<PROJECT_ID>-tfstate" \
  -backend-config="prefix=prod"
terraform fmt -check
terraform validate
terraform plan -out plan.tfplan
```

Review the plan with `@terraform-reviewer` / `@gcp-architect`. **`apply` and `destroy`
require explicit human approval (ADR-043) and are never run from an agent harness.**

## Before the first Cloud Run revision goes healthy

Add a version to each of the 6 manual secrets (runbook Fase 3). At minimum the 4
`revenueflow-whatsapp-*` secrets; the 2 `revenueflow-langfuse-*` are only mounted
when `tracer_sink = "langfuse"`.

## Consumption model

`ADR-047`: the API service also runs the pull consumer
(`worker.subscriber.run_subscriber()` started in `main.lifespan`), so
`min_instances >= 1`. Starting that task is a companion **application** change,
not Terraform — Terraform alone deploys an API that publishes and never consumes.

## Known trade-offs (V1)

- Cloud SQL is `ZONAL` (no HA) with a public IP + empty authorized networks; access
  is via the Cloud SQL connector / Auth Proxy. Switch: `availability_type = "REGIONAL"`,
  private IP + PSA.
- `allUsers` `run.invoker` exposes every route; the webhook HMAC check is the control.
- The DB password is in Terraform state and in two secrets. Verify the state bucket's
  IAM manually.
