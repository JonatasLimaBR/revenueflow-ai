# Deploy no GCP — Runbook

Provisiona o RevenueFlow no GCP a partir de `infra/terraform/` e do `Dockerfile`.
Contexto: ADR-001 (GCP), ADR-002 (Cloud Run), ADR-004 (Cloud SQL), ADR-006 (Pub/Sub),
ADR-027 (GCP System of Record), ADR-043 (`apply`/`destroy` nunca de agente).

Primeiro deploy roda em **`LLM_STUB=1`** (sem Gemini real). Vertex real é a feature
`WHATSAPP_INBOUND_VERTEX`.

## Fase 0 — Pré-requisitos (máquina local)

1. Instalar Google Cloud CLI e Terraform `>= 1.7`.
2. `gcloud auth login` e `gcloud auth application-default login` (ADC para o Terraform).
3. Projeto + billing:
   ```
   gcloud projects create <PROJECT_ID> --name="RevenueFlow"
   gcloud billing projects link <PROJECT_ID> --billing-account=<BILLING_ACCOUNT>
   gcloud config set project <PROJECT_ID>
   ```
4. Habilitar APIs (idempotente; também há `google_project_service` no Terraform):
   ```
   gcloud services enable run.googleapis.com sqladmin.googleapis.com \
     pubsub.googleapis.com secretmanager.googleapis.com \
     artifactregistry.googleapis.com aiplatform.googleapis.com \
     cloudbuild.googleapis.com iam.googleapis.com compute.googleapis.com
   ```

## Fase 1 — Bootstrap (state + registry) — fora do Terraform, uma vez

5. Bucket do state:
   ```
   gcloud storage buckets create gs://<PROJECT_ID>-tfstate --location=<REGION> --uniform-bucket-level-access
   gcloud storage buckets update  gs://<PROJECT_ID>-tfstate --versioning
   ```
6. Artifact Registry:
   ```
   gcloud artifacts repositories create revenueflow --repository-format=docker --location=<REGION>
   ```

## Fase 2 — Terraform: preparar e revisar

7. `cd infra/terraform`
8. Backend GCS em `backend.tf`:
   ```hcl
   terraform { backend "gcs" { bucket = "<PROJECT_ID>-tfstate" prefix = "prod" } }
   ```
9. `terraform.tfvars` (**sem segredos**, git-ignored):
   ```hcl
   project_id     = "<PROJECT_ID>"
   region         = "<REGION>"
   image          = "<REGION>-docker.pkg.dev/<PROJECT_ID>/revenueflow/api:<SHA>"
   ```
10. `terraform init && terraform fmt && terraform validate && terraform plan -out plan.tfplan`
11. Revisão: `@terraform-reviewer` (IAM least-privilege, sem secrets em tfvars,
    `deletion_protection`, state separado por ambiente) + `@gcp-architect` (aderência aos ADRs).
    **`apply` e `destroy` exigem aprovação humana explícita no terminal (ADR-043).**

## Fase 3 — Segredos

12. O Terraform cria os *containers*; os valores entram à mão:
    ```
    printf '%s' "$WA_APP_SECRET"     | gcloud secrets versions add revenueflow-whatsapp-app-secret     --data-file=-
    printf '%s' "$WA_ACCESS_TOKEN"   | gcloud secrets versions add revenueflow-whatsapp-access-token   --data-file=-
    printf '%s' "$WA_VERIFY_TOKEN"   | gcloud secrets versions add revenueflow-whatsapp-verify-token   --data-file=-
    printf '%s' "$WA_PHONE_NUMBER_ID"| gcloud secrets versions add revenueflow-whatsapp-phone-number-id --data-file=-
    ```

## Fase 4 — Build e push da imagem

13. ```
    gcloud auth configure-docker <REGION>-docker.pkg.dev
    SHA=$(git rev-parse --short HEAD)
    docker build -t <REGION>-docker.pkg.dev/<PROJECT_ID>/revenueflow/api:$SHA .
    docker push  <REGION>-docker.pkg.dev/<PROJECT_ID>/revenueflow/api:$SHA
    ```
    (ou `gcloud builds submit`.) A imagem no Cloud Run é sempre `:<SHA>`, nunca `:latest`.

## Fase 5 — `terraform apply` (aprovação humana)

14. `terraform apply plan.tfplan`. **Cloud SQL leva ~10 min.** Provisiona: service account
    dedicada + IAM (`pubsub.publisher`, `pubsub.subscriber`, `cloudsql.client`,
    `secretmanager.secretAccessor`, `aiplatform.user`), tópico + subscription Pub/Sub,
    instância + database Cloud SQL, secrets, serviço Cloud Run v2.

## Fase 6 — Migrar o banco

15. Cloud SQL Auth Proxy local (ou um Cloud Run Job com a mesma imagem):
    ```
    ./cloud-sql-proxy <PROJECT_ID>:<REGION>:revenueflow-api-oltp &
    DATABASE_URL="postgresql://revenueflow:<PW>@127.0.0.1:5432/revenueflow" python scripts/migrate.py
    DATABASE_URL=... python scripts/seed.py
    ```

## Fase 7 — Config do Cloud Run

16. `template` do `google_cloud_run_v2_service`:
    - `service_account` = a SA dedicada.
    - `env`: `PUBSUB_PROJECT_ID=<PROJECT_ID>`, `TRACER_SINK=langfuse`, `CHANNEL_OUTBOUND=real`,
      **`LLM_STUB=1`**, `GEMINI_MODEL`, `VERTEX_AI_LOCATION`.
    - `DATABASE_URL` via socket do Cloud SQL: anexar a instância
      (`annotations["run.googleapis.com/cloudsql-instances"]` ou volume) e usar
      `postgresql://revenueflow:<pw>@/revenueflow?host=/cloudsql/<conn-name>`.
    - Secrets via `env { value_source { secret_key_ref {...} } }` para os 4 secrets do WhatsApp
      e as chaves do Langfuse.
    - `scaling.min_instance_count`: ver decisão abaixo.
17. Entrega Pub/Sub → worker — **decisão de arquitetura**: o `worker/subscriber.py` atual é um
    *pull loop*. Em Cloud Run:
    - **push (recomendado):** subscription push → endpoint interno `/internal/consume`
      autenticado com OIDC da SA do Pub/Sub (`run.invoker`). Escala a zero. Requer um handler
      novo (não existe ainda).
    - **pull:** `min_instance_count = 1` e iniciar `run_subscriber()` no `lifespan`. Simples,
      mas paga instância parada.
18. Invoker: o webhook (`/webhook/whatsapp`) é público (`allUsers`) — a verificação de
    assinatura HMAC já é o controle. O endpoint de consumo (se push) é privado.

## Fase 8 — Webhook do WhatsApp

19. No WhatsApp Business Platform: callback URL = `https://<cloud-run-url>/webhook/whatsapp`,
    verify token = o valor do secret. O handshake `GET` já está implementado.

## Fase 9 — Observabilidade e custo

20. **Langfuse** (ADR-045): deploy separado (Cloud Run + Cloud SQL próprio) ou SaaS. Setar
    `LANGFUSE_HOST` + keys como env/secret e `TRACER_SINK=langfuse`. Enquanto não existir,
    `TRACER_SINK=otel` ou `noop`.
21. Budget alert (skill `finops`): `gcloud billing budgets create --billing-account=<BA> ...`.

## Fase 10 — CI/CD

22. Trigger do Cloud Build em merge na `main`:
    `build → push :<sha> → terraform plan (gated) → terraform apply → gcloud run deploy`.
    Deploy nunca automático sem gate humano.

---

## Lacunas nos stubs `infra/terraform/` (preencher antes do `apply`)

- `backend "gcs"` (state remoto)
- `google_project_service` para as APIs
- recurso `google_artifact_registry_repository`
- conexão Cloud Run ↔ Cloud SQL (annotation / volume)
- `env` + `secret_key_ref` no Cloud Run
- secrets `whatsapp-verify-token` e `whatsapp-phone-number-id`
- mecanismo de entrega Pub/Sub → worker (push endpoint + IAM, ou pull + min-instances)
- `google_cloud_run_v2_service_iam_member` (público no webhook, privado no consumo)
- hospedagem do Langfuse

## Rollback

- Cloud Run: `gcloud run services update-traffic revenueflow-api --to-revisions=<prev>=100`.
- Terraform: `terraform apply` de um `plan` do commit anterior (nunca `destroy` das tabelas —
  `deletion_protection` no Cloud SQL).
