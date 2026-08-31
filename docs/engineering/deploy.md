# Deploy no GCP — Runbook

Provisiona o RevenueFlow no GCP a partir de `infra/terraform/` e do `Dockerfile`.
Contexto: ADR-001 (GCP), ADR-002 (Cloud Run), ADR-004 (Cloud SQL), ADR-006 (Pub/Sub),
ADR-027 (GCP System of Record), ADR-043 (`apply`/`destroy` nunca de agente),
**ADR-048 (CD via GitHub Actions + WIF, sem chave)**.

Primeiro deploy roda em **`LLM_STUB=1`** (sem Gemini real). Vertex real é a feature
`WHATSAPP_INBOUND_VERTEX`.

Modelo (ADR-048): **um bootstrap manual, uma vez**; depois todo `terraform plan`/`apply` e o
build da imagem rodam no GitHub Actions, autenticando por Workload Identity Federation —
nenhuma chave de service account em lugar nenhum.

## Fase 0 — Pré-requisitos (máquina local, humano)

1. Instalar Google Cloud CLI e Terraform `>= 1.7`.
2. `gcloud auth login` e `gcloud auth application-default login`.
3. Projeto + billing (precisa de billing admin):
   ```
   gcloud projects create <PROJECT_ID> --name="RevenueFlow"
   gcloud billing accounts list
   gcloud billing projects link <PROJECT_ID> --billing-account=<BILLING_ACCOUNT>
   gcloud config set project <PROJECT_ID>
   ```

## Fase 1 — Bootstrap keyless (uma vez, ADR-048)

4. Roda com a sua identidade de admin. Cria o bucket de state, o Workload Identity pool/provider
   e a service account `revenueflow-deployer`:
   ```
   cd infra/terraform/bootstrap
   terraform init
   terraform apply -var project_id=<PROJECT_ID> -var region=<REGION>
   ```
   (state deste módulo é local e git-ignored — ver `infra/terraform/bootstrap/README.md`.)
5. Copie os `outputs` para as **Variables** do repo (Settings → Secrets and variables → Actions
   → Variables): `WIF_PROVIDER`, `DEPLOY_SA`, `TF_STATE_BUCKET`, `GCP_PROJECT_ID`, `GCP_REGION`.
6. Crie o **Environment `production`** (Settings → Environments) com você como **required
   reviewer** — essa aprovação é a barreira do ADR-043 sobre o `terraform apply`.

## Fase 2 — Daqui em diante é PR

7. Mudanças em `infra/terraform/**` disparam `.github/workflows/terraform.yml`:
   - **PR:** job `plan` — `init` (backend GCS via `TF_STATE_BUCKET`), `validate`, `plan`, e o
     plan é postado como comentário no PR. Revisar com `@terraform-reviewer` (IAM
     least-privilege, `deletion_protection`) + `@gcp-architect` (aderência aos ADRs).
   - **Merge na `main`:** job `deploy` (`environment: production`) — build + push da imagem
     `:<sha>` por WIF, depois `terraform apply`. Só roda **após a aprovação** do Environment.
   O `plan`/`deploy` só executam quando `WIF_PROVIDER` está setado (senão o job é `skipped`).

## Fase 3 — Segredos

12. O Terraform cria os *containers*; os valores entram à mão:
    ```
    printf '%s' "$WA_APP_SECRET"     | gcloud secrets versions add revenueflow-whatsapp-app-secret     --data-file=-
    printf '%s' "$WA_ACCESS_TOKEN"   | gcloud secrets versions add revenueflow-whatsapp-access-token   --data-file=-
    printf '%s' "$WA_VERIFY_TOKEN"   | gcloud secrets versions add revenueflow-whatsapp-verify-token   --data-file=-
    printf '%s' "$WA_PHONE_NUMBER_ID"| gcloud secrets versions add revenueflow-whatsapp-phone-number-id --data-file=-
    ```

## Fase 4 — Build da imagem

13. É o job `deploy` do workflow: `docker build` + `docker push` para
    `<REGION>-docker.pkg.dev/<PROJECT_ID>/revenueflow/api:<sha do commit>`, autenticando por
    WIF. A imagem no Cloud Run é sempre `:<sha>`, nunca `:latest`. Nada manual.

## Fase 5 — `terraform apply` (via Environment `production`)

14. No merge à `main`, o job `deploy` fica pendente até você **aprovar o Environment
    `production`** (ADR-043). Aprovado, roda `terraform apply` (que também atualiza o Cloud Run
    com a nova imagem). **Cloud SQL leva ~10 min no primeiro apply.** Provisiona: service
    account de runtime + IAM (pubsub/cloudsql/secretAccessor, escopados), tópico + DLQ +
    subscription Pub/Sub `revenueflow.messages`, instância + database Cloud SQL, secrets,
    serviço Cloud Run v2.

## Fase 6 — Migrar o banco

15. Cloud SQL Auth Proxy local (ou um Cloud Run Job com a mesma imagem):
    ```
    ./cloud-sql-proxy <PROJECT_ID>:<REGION>:revenueflow-api-oltp &
    DATABASE_URL="postgresql://revenueflow:<PW>@127.0.0.1:5432/revenueflow" python scripts/migrate.py
    DATABASE_URL=... python scripts/seed.py
    ```

## Fase 7 — Config do Cloud Run

16. Já está no `cloud_run.tf`: `service_account` dedicada, `env` (`PUBSUB_PROJECT_ID`,
    `TRACER_SINK`, `CHANNEL_OUTBOUND=real`, `LLM_STUB=1`, `GEMINI_MODEL`, `VERTEX_AI_LOCATION`,
    `LANGFUSE_HOST`), `DATABASE_URL` via secret `revenueflow-database-url` (DSN com socket
    `/cloudsql/<conn>`), `secret_key_ref` para os 4 secrets do WhatsApp (+ os 2 do Langfuse
    quando `tracer_sink=langfuse`), volume do Cloud SQL, e `min_instance_count = var.min_instances`.
17. **Entrega Pub/Sub → worker: decidido pelo ADR-047** — pull, com `min_instances >= 1`, e o
    consumidor roda no mesmo serviço (`run_subscriber()` iniciado no `main.lifespan`). Isso é uma
    mudança de **código do app** (companheira deste PR de infra); Terraform sozinho entrega um
    serviço que publica e não consome.
18. Invoker: `allUsers` `run.invoker` (`cloud_run.tf`) — a verificação de assinatura HMAC do
    webhook é o controle (ADR-016/031).

## Fase 8 — Webhook do WhatsApp

19. No WhatsApp Business Platform: callback URL = `https://<cloud-run-url>/webhook/whatsapp`,
    verify token = o valor do secret. O handshake `GET` já está implementado.

## Fase 9 — Observabilidade e custo

20. **Langfuse** (ADR-045): deploy separado (Cloud Run + Cloud SQL próprio) ou SaaS. Setar
    `LANGFUSE_HOST` + keys como env/secret e `TRACER_SINK=langfuse`. Enquanto não existir,
    `TRACER_SINK=otel` ou `noop`.
21. Budget alert: `budget.tf` cria um `google_billing_budget` (50/90/100%) quando
    `var.billing_account` é setado; só alerta, não limita.

## Fase 10 — CI/CD

22. `.github/workflows/terraform.yml` (ADR-048): `plan` em PR que toca `infra/terraform/**`
    (comentado no PR); `deploy` em merge na `main` — build+push da imagem por WIF, depois
    `terraform apply`, gated pelo Environment `production`. `terraform apply` atualiza o Cloud
    Run com a nova imagem — não há `gcloud run deploy` separado.

---

## O que ainda falta antes de um deploy funcional

- **Bootstrap (Fase 1):** rodar `infra/terraform/bootstrap` uma vez e setar as 5 Variables +
  o Environment `production` no repo.
- **Terraform:** o primeiro `plan` no workflow (num projeto real) + revisão `@terraform-reviewer`.
- **Segredos:** popular as 6 versões (`gcloud secrets versions add`) — 4 WhatsApp sempre, 2
  Langfuse se `tracer_sink=langfuse`.
- **Langfuse:** decidir hospedagem (Cloud Run próprio vs SaaS) — enquanto isso `tracer_sink=noop`.
- **Billing budget:** o `google_billing_budget` precisa de binding no billing account para a SA
  `deployer`, ou fica manual.
- **VPC/private IP** para Cloud SQL, `availability_type=REGIONAL`, uptime check + alerta —
  trade-offs de V1 aceitos; ver `infra/terraform/README.md`.

## Rollback

- Cloud Run: `gcloud run services update-traffic revenueflow-api --to-revisions=<prev>=100`.
- Terraform: `terraform apply` de um `plan` do commit anterior (nunca `destroy` das tabelas —
  `deletion_protection` no Cloud SQL).
