# ADR-048 — CD via GitHub Actions + Workload Identity Federation, sem chave

## Status
Accepted

## Contexto
O deploy no GCP (`docs/engineering/deploy.md`, ADR-002/047) precisa de um mecanismo para rodar
`terraform plan`/`apply` e publicar a imagem. As opções vão de `terraform apply` no laptop do dev
(com ADC ou chave de service account) até um pipeline dedicado. O repositório já vive no GitHub,
todo o CI está no GitHub Actions, a `main` é protegida e "o portão é o CI, não a revisão"
(ADR-046 / CLAUDE.md). ADR-043 exige aprovação humana explícita para `apply`.

## Decisão
O CD roda no **GitHub Actions**, autenticando no GCP por **Workload Identity Federation** —
troca do token OIDC do Actions por um token de curta duração de uma service account `deployer`.
**Nenhuma chave de service account é criada, baixada ou armazenada.**

- Um Terraform de **bootstrap** (`infra/terraform/bootstrap/`) cria, **uma vez** e com a
  identidade de admin do usuário no terminal: o bucket de state, o Workload Identity Pool +
  Provider (com *attribute condition* travando no repo `JonatasLimaBR/revenueflow-ai`), a
  service account `deployer` com os roles project-scoped que a config principal precisa, e o
  binding `roles/iam.workloadIdentityUser`.
- O workflow `.github/workflows/terraform.yml`: job `plan` em PR que toca `infra/terraform/**`
  (posta o plan como comentário); job `apply` em push na `main`, protegido por um **GitHub
  Environment `production` com reviewer obrigatório** — essa aprovação é a barreira do ADR-043.
- Valores de secret entram fora do CI (`gcloud secrets versions add` / console). O Terraform
  cria os *containers*; os *valores* nunca passam por variável de CI.

## Alternativas consideradas
- **`terraform apply` local (laptop)** — state e credenciais no disco do dev, sem trilha de
  auditoria, "funciona na minha máquina". Aceitável só para o bootstrap e break-glass.
- **Chave de service account (JSON) como secret do GitHub** — chave de longa duração para
  vazar/rotacionar; é exatamente o que os scanners de segredo procuram.
- **Cloud Build** — segundo sistema de CI para manter; o código e todo o resto do CI já estão
  no GitHub.
- **Terraform Cloud / Spacelift / Atlantis** — mais um fornecedor e superfície; excessivo para
  a V1.

## Motivo
Sem chave elimina a classe inteira de incidentes de key management. Todo `apply` fica amarrado a
um commit/PR com logs. O `plan` é revisado no PR. A aprovação do `apply` vira um gate nativo do
GitHub (Environment), consistente com o ADR-043 e com a proteção de `main`. Um único sistema
de CI.

## Consequências
- O bootstrap exige **uma** execução local do Terraform com identidade de admin (Project IAM
  Admin + Storage Admin no projeto). Depois disso, nada mais usa chave.
- A SA `deployer` recebe roles amplos (`run.admin`, `cloudsql.admin`, `pubsub.admin`,
  `secretmanager.admin`, `artifactregistry.admin`, `iam.serviceAccountAdmin`,
  `serviceusage.serviceUsageAdmin`, `resourcemanager.projectIamAdmin`, `storage.admin`) — amplos,
  mas escopados a **um projeto** e só assumíveis a partir de **um repositório** via OIDC.
- O orçamento (`google_billing_budget`) precisa de permissão no billing account, fora do escopo
  da `deployer`; fica como passo manual ou um segundo binding explícito.
- O state do próprio `bootstrap/` fica local (git-ignored) — documentado.
- Requer configurar no repositório: as *Variables* `WIF_PROVIDER`, `DEPLOY_SA`,
  `TF_STATE_BUCKET`, `GCP_PROJECT_ID`, `GCP_REGION`, e o Environment `production` com reviewer.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
