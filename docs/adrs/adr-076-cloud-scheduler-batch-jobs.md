# ADR-076 — Cloud Scheduler encadeando os 4 jobs batch

## Status
Accepted

## Contexto
`opportunity_scan`/`campaign_run`/`lead_sweep`/`analytics_sync` (ADR-053/059/061/062) só rodavam
sob demanda via `gcloud run jobs execute` desde que foram criados — cada ADR documentou o Cloud
Scheduler como follow-up explícito, nunca implementado. Usuário pediu explicitamente pra fechar
essa lacuna.

## Decisão

- **1 `google_cloud_scheduler_job` por Job existente** (`scheduler.tf`, novo), via o padrão oficial
  do GCP pra invocar um Cloud Run Job — `http_target` `POST` na API v1 de Jobs
  (`.../namespaces/{project}/jobs/{job}:run`) com um `oauth_token` — não há atalho
  agendamento-nativo no `google_cloud_run_v2_job` deste provider.
- **Ordem encadeada por horário, não por dependência explícita do Terraform**: `opportunity_scan`
  às 09:00 UTC, `campaign_run` 30 min depois (09:30 UTC — consome as oportunidades que o scan
  acabou de gerar, ADR-020 Policy Gate), `lead_sweep` às 09:15 UTC (independente), `analytics_sync`
  às 22:00 UTC (fim do dia). Cloud Scheduler não tem "rodar depois que o job X terminar" nativo —
  a folga de 30 min entre scan e campaign é a mitigação (cada scan real leva segundos a poucos
  minutos, folga generosa).
- **Service account dedicada `revenueflow-api-scheduler`** (ADR-008 least privilege) — só
  `roles/run.invoker` nos 4 Jobs específicos via `google_cloud_run_v2_job_iam_member`, nunca a SA
  de runtime da própria API (`google_service_account.api`), que não deveria também poder disparar
  jobs batch.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Retry/alertas específicos de agendamento além do que os Jobs já têm (`max_retries = 1`) — a
  suíte de alertas do ADR-056 (`no_turns`, `tool_failures`) já cobre ausência de atividade.
- Dependência explícita entre schedules (ex: Cloud Workflows orquestrando a ordem) — a folga fixa
  de horário é suficiente pro volume atual; reconsiderar se o scan passar a demorar mais que 30 min.

## Alternativas consideradas

- **Cron dentro do próprio container** (ex: `croniter` num loop, ou um sidecar) — rejeitada:
  reintroduziria um processo de longa duração fora do modelo request/Job já estabelecido pros
  batch jobs (ADR-019/020), sem ganho sobre o agendador nativo do GCP.
- **Cloud Workflows orquestrando a sequência** — mais robusto pra dependência explícita
  scan→campaign, mas é um serviço a mais pra manter só pra uma folga de 30 minutos; reconsiderar se
  o scan passar a demorar tempo suficiente pra colidir com o horário do campaign.
- **SA de runtime da API (`google_service_account.api`) também com `roles/run.invoker`** —
  rejeitada por escopo: essa SA já tem acesso amplo (Cloud SQL, Vertex AI, BigQuery, secrets); dar a
  ela também permissão de disparar Jobs violaria o least privilege do ADR-008 sem necessidade — uma
  SA dedicada e escopada por-job custa zero a mais.

## Motivo
Fecha uma lacuna documentada há 3 ADRs sem custar infraestrutura nova além do Cloud Scheduler em
si (grátis até 3 jobs, e mesmo acima disso o custo é centavos/mês) — os 4 Jobs e a lógica de
negócio já existiam.

## Consequências
- +1 arquivo (`scheduler.tf`: 1 service account, 4 `google_cloud_run_v2_job_iam_member`, 4
  `google_cloud_scheduler_job`); `apis.tf` += `cloudscheduler.googleapis.com`; +ADR-076.
- Sem migração, sem dependência Python nova.
- A partir do próximo deploy, os 4 jobs passam a rodar automaticamente todo dia — `consent_opt_in_at`
  ainda vazio pra clientes reais significa que `campaign_run` roda mas não envia nada de fato
  (comportamento correto, documentado desde ADR-059).

## Regra de revisão
Mudanças nesta decisão — em especial dar à SA de runtime da API permissão pra disparar jobs, ou
remover o escopo por-job do `roles/run.invoker` — exigem novo ADR ou superseding ADR.
