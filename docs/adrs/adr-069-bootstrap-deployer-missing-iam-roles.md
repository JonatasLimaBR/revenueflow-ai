# ADR-069 — Bootstrap: `deployer_roles` estava sem Logging/Monitoring/Compute admin

## Status
Accepted

## Contexto
O usuário reportou "não tem nada de dash no projeto... está muito estranho" e pediu uma auditoria.
A auditoria revelou dois problemas empilhados, não um só:

1. **O ambiente GitHub `production` tinha uma regra `required_reviewers`** (configurada desde o
   bootstrap do CD, 2026-08-31) que pausa o job `deploy` até aprovação manual. Ninguém aprovava —
   17 deploys ficaram empilhados em `waiting` desde **2026-09-03**, o último deploy real bem
   sucedido foi CUSTOMER_360. Tudo entregue depois disso (OPPORTUNITY_ENGINE, HUMAN_HANDOFF,
   AUDIT_TRAIL, **OBSERVABILITY_OPS**, HARDENING_*, ACTIVE_SALES, **LANDING_PAGE**, ANALYTICS,
   LEAD_LIFECYCLE, ANALYTICS_360, **DASHBOARD_ACCESS**, MCP_SERVER, WHATSAPP_CTA,
   MCP_READONLY_PUBLIC, **LANDING_PAGE_DOMAIN**) existia só como código — nunca chegou a ser
   criado no GCP.
2. **Depois de aprovar o deploy mais recente, o `apply` falhou de verdade** — `local.deployer_roles`
   em `infra/terraform/bootstrap/main.tf` nunca incluiu `roles/logging.admin`,
   `roles/monitoring.admin` ou `roles/compute.admin`. A service account que a CI usa (via WIF,
   ADR-048) não tinha permissão pra criar `google_logging_metric`, `google_monitoring_dashboard`,
   `google_monitoring_alert_policy` (ADR-056) nem os recursos de Load Balancer da landing page —
   `google_compute_global_address`/`google_compute_url_map`/`google_compute_target_http_proxy`/
   `google_compute_global_forwarding_rule`/`google_compute_managed_ssl_certificate` (ADR-060/068).
   Esse gap nunca foi pego porque, pelo item 1, nenhum `apply` real tinha rodado desde antes de
   essas fatias existirem.

## Decisão

- **`deployer_roles` (bootstrap) ganha 3 papéis**: `roles/logging.admin`,
  `roles/monitoring.admin`, `roles/compute.admin` — mesmo padrão `*.admin` já usado pra todo outro
  serviço nessa lista (a service account de deploy precisa criar/gerenciar qualquer recurso do
  tipo, então least-privilege granular não é o objetivo aqui — esse é o objetivo da service
  account de *runtime*, `google_service_account.api`, tratada à parte em `iam.tf`).
- **`infra/terraform/bootstrap/` continua sendo aplicado manualmente**, fora da CI (ADR-048: "um
  bootstrap manual, uma vez"). Essa correção exige um segundo `apply` manual do bootstrap, com uma
  identidade Owner/IAM Admin do projeto — não a service account de deploy (que não pode conceder
  papéis pra si mesma retroativamente sem essa mesma correção já aplicada).

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Trocar a regra `required_reviewers` do ambiente `production` — o gate em si é uma decisão de
  segurança válida (aprovação humana antes de aplicar em produção); o problema não era o gate
  existir, era ninguém estar aprovando. Ajustar isso é uma decisão de processo do usuário, não do
  código.
- Escopar os 3 papéis novos mais estritamente (ex.: `roles/logging.configWriter` em vez de
  `logging.admin`) — mantém consistência com o padrão já estabelecido nesta lista específica; uma
  revisão de least-privilege pra `deployer_roles` como um todo é um follow-up separado.

## Alternativas consideradas

- **Conceder os papéis manualmente via `gcloud` uma vez, sem tocar o Terraform** — corrigiria o
  estado atual mas deixaria o bootstrap desalinhado do estado real; qualquer recriação futura da
  service account de deploy reproduziria o mesmo bug. Corrigir no código é a fonte da verdade.
- **Mover a criação desses recursos de Monitoring/Compute pra um módulo separado com sua própria
  service account mais restrita** — complexidade desproporcional ao problema; o padrão já
  estabelecido (uma SA de deploy ampla, *.admin por serviço) é intencional pra V1.

## Motivo
O gap existia desde a fatia OBSERVABILITY_OPS (2026-09-03) mas só foi descoberto agora porque essa
foi a primeira vez, nesta sessão, que um `apply` real chegou a rodar contra essas mudanças — a
auditoria pedida pelo usuário revelou os dois problemas encadeados de uma vez.

## Consequências
- +3 roles em `infra/terraform/bootstrap/main.tf::local.deployer_roles`; +ADR-069.
- Exige um `terraform apply` manual do bootstrap (fora da CI) antes que o próximo deploy consiga
  criar os recursos de Monitoring/Compute que já estavam no código há dias.
- Depois desse apply, o próximo push em `main` (ou um `workflow_dispatch` manual) precisa passar de
  novo pelo gate de aprovação do ambiente `production` — o gate em si não muda.

## Regra de revisão
Mudanças nesta decisão — em especial remover algum desses 3 papéis, ou mudar o modelo de uma SA de
deploy ampla pra múltiplas SAs escopadas por serviço — exigem novo ADR ou superseding ADR.
