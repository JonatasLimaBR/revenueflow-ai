# ADR-075 — Langfuse self-hosted em produção (ADR-045 emendado)

## Status
Accepted

## Contexto
ADR-045 colocou Langfuse self-hosted atrás da porta `Tracer`, mas só como container local
(`docker-compose.yml`). Uma auditoria (2026-09-08) confirmou que produção nunca chegou a apontar
pra lá: `TRACER_SINK` real no Cloud Run ficou em `noop` mesmo depois do ADR-056 documentar a troca
pra `otel` — Cloud Trace conferido vazio via API. Usuário pediu explicitamente pra resolver, e
escolheu self-hosted completo (controle total) em vez de Langfuse Cloud SaaS.

## Decisão

- **Novo serviço Cloud Run `revenueflow-api-langfuse`** (`langfuse_service.tf`), mesma imagem
  pública `langfuse/langfuse:2` do `docker-compose.yml` local — sem build próprio, sem Artifact
  Registry.
- **Banco próprio no mesmo Cloud SQL** (`cloud_sql.tf`): `google_sql_database`/`google_sql_user`
  `langfuse` na instância `oltp` já existente, em vez de uma segunda instância — mesmo padrão de
  reaproveitamento do banco da app.
- **DSN via IP público da instância, não socket unix** — o cliente Prisma/Node do Langfuse não fala
  a convenção `?host=/cloudsql/...` que os pools `psycopg` da app usam; a instância já tem
  `ipv4_enabled=true`/`ssl_mode=ENCRYPTED_ONLY`, então `postgresql://langfuse:...@<public_ip>:5432/langfuse?sslmode=require`
  reaproveita exposição que já existe, sem abrir superfície nova.
- **Subdomínio fixo `langfuse.mastavista.com.br`** (`subdomains.tf`/`landing_page.tf`, mesmo padrão
  Serverless NEG + backend service + host_rule do ADR-074) em vez da URL `*.run.app` gerada pelo
  Cloud Run — resolve de saída o problema do ovo-e-galinha do `NEXTAUTH_URL` (o Next.js/NextAuth do
  Langfuse precisa saber a própria URL externa antes do primeiro boot; a URL `*.run.app` só existe
  depois do serviço já criado, um subdomínio fixo é conhecido em tempo de `plan`). Certificado
  gerenciado ganha esse 4º domínio (mesma janela de reprovisionamento já aceita no ADR-074).
- **3 secrets novos Terraform-gerados** (`secrets.tf`, mesmo padrão dos tokens
  approval/handoff/mcp/portal_session — não travam o deploy num passo manual):
  `revenueflow-langfuse-database-url`, `revenueflow-langfuse-nextauth-secret`,
  `revenueflow-langfuse-salt`.
- **`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` continuam manuais** (já reservados em
  `local.manual_secrets` desde antes) — só existem depois que alguém loga no Langfuse pela primeira
  vez e gera o par de API keys pela própria UI; não dá pra automatizar isso no `apply`.
- **`var.tracer_sink` continua `noop` nesta fatia** — vira `langfuse` numa mudança de `tfvars`
  separada, só depois do passo manual acima. `var.langfuse_host` já aponta pro subdomínio fixo por
  default, então essa troca de `tfvars` fica só o `tracer_sink` em si.
- **`AUTH_DISABLE_SIGNUP` controlado por `var.langfuse_disable_signup`** (default `false`) —
  signup aberto até o usuário criar a 1ª conta admin; vira `true` numa troca de `tfvars` depois
  disso, mesmo padrão de "infra pronta, flag vira depois" do `dashboard_viewer_emails`.
- **`allUsers` invoker** no Cloud Run, mesmo modelo de confiança do portal/MCP público — o próprio
  login do Langfuse (email+senha) é o gate, não IAM.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Automatizar a criação da conta admin / par de API keys via Terraform — exigiria a API do Langfuse
  responder num apply, não é o papel do Terraform.
- Trocar `var.tracer_sink` pra `langfuse` neste PR — só depois do usuário logar e gerar as keys.
- Cloud SQL instância dedicada pro Langfuse — reaproveitar a instância já existente é suficiente e
  mais barato (mesmo raciocínio do banco da app).
- IAP ou identidade por pessoa no Langfuse — mesmo modelo público + auth de app do portal/MCP.

## Alternativas consideradas

- **Langfuse Cloud (SaaS)** — rejeitada: usuário pediu explicitamente controle total, sem dado de
  produção saindo do próprio GCP.
- **VPC connector + IP privado do Cloud SQL** — mais "correto" de rede, mas exige provisionar um
  Serverless VPC Access connector novo só pra isso; o IP público + SSL já é o padrão que a própria
  instância expõe hoje (usado pra migração/dev local), sem superfície nova.
- **URL `*.run.app` do próprio Cloud Run pro `NEXTAUTH_URL`** — inviável sem um passo manual de
  atualização pós-criação (a URL só existe depois do 1º apply); o subdomínio fixo evita esse
  problema de raiz.

## Motivo
Fecha a lacuna que a auditoria do ADR-069/070 encontrou (produção nunca rodou `otel` nem
`langfuse` de verdade) com a opção que o usuário escolheu — self-hosted, controle total — e reusa
100% da infra já existente (instância Cloud SQL, Load Balancer, certificado) em vez de provisionar
componentes novos.

## Consequências

- +1 arquivo (`langfuse_service.tf`: serviço Cloud Run + invoker público); `cloud_sql.tf` += banco
  e usuário `langfuse`; `secrets.tf` += 3 secrets Terraform-gerados + IAM; `subdomains.tf` += NEG +
  backend service; `landing_page.tf` += host_rule/path_matcher + domínio no certificado;
  `variables.tf` += `langfuse_disable_signup`, `langfuse_host` aponta pro subdomínio fixo por
  default; `outputs.tf` += `langfuse_domain_url`; +ADR-075.
- Certificado gerenciado recriado no próximo `apply` (mesma janela do ADR-074, já aceita).
- Pendência operacional nova: registro DNS A (`langfuse.mastavista.com.br` → mesmo
  `landing_page_ip`); depois do DNS resolver e o cert ficar `ACTIVE`, abrir a URL e criar a 1ª conta
  admin; gerar o par de API keys na UI do Langfuse; `gcloud secrets versions add` em
  `revenueflow-langfuse-public-key`/`revenueflow-langfuse-secret-key`; trocar `var.tracer_sink` pra
  `"langfuse"` e (opcional) `var.langfuse_disable_signup` pra `true`.
- Sem dependência nova, sem build de imagem próprio (imagem pública `langfuse/langfuse:2` direto).

## Regra de revisão
Mudanças nesta decisão — em especial migrar pra uma instância Cloud SQL dedicada, remover o
subdomínio fixo em favor da URL `*.run.app`, ou automatizar o par de API keys sem um passo manual —
exigem novo ADR ou superseding ADR.
