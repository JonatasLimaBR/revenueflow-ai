# ADR-056 — OBSERVABILITY_OPS: OTel → Cloud Trace de produção + métricas via log-based metrics

## Status
Accepted

## Contexto
A AUDIT_TRAIL (ADR-055) deu **persistência por turno** (`audit_event` + `v_ai_cost_per_conversation`
/ `v_ai_cost_per_outcome`), mas a SPEC-034 continua sem entregar:

- **Nada disso chega a Cloud Monitoring.** `audit_event` está no Cloud SQL, que não é fonte nativa
  de métrica — não há dashboard nem alerta. A SPEC-034 pede `request_count`, `response_time`,
  `error_rate`, `tool_failures`, `token_usage`, `cost`, `handoffs` + "dashboards e alertas
  básicos".
- **Produção roda `TRACER_SINK=noop`.** `OTelTracer` e `LangfuseTracer` estão implementados e
  testados, mas nenhum `TracerProvider` global é configurado — mesmo com `TRACER_SINK=otel` os
  spans iriam para um tracer no-op. O waterfall por-span do turno é descartado em prod (ADR-040
  pela metade).
- **`cost.py::MODEL_PRICES` era placeholder** — o `cost_usd` do audit (e o KPI de custo, ADR-023)
  valia o que ele valesse.
- **A view "custo de IA / receita"** (PRD-013) foi adiada da AUDIT_TRAIL para cá.

Restrições: mínimo de infra nova (postura de toda fatia da V1); no máximo **uma** dependência
nova; `mypy --strict`; a suíte roda só com `postgres:16` sem credencial de nuvem; `main`
protegida com `terraform plan` no PR; PII minimizada (SPEC-031, ADR-032); custo é cálculo
determinístico e offline (ADR-009).

## Decisão

- **Plano de métrica = log-based metrics + métricas nativas do Cloud Run; sem job de push (DA1).**
  `AuditTracer.flush()` emite **uma** linha JSON `audit.turn` por turno, ao lado do `persist`,
  com os campos que o `AuditEvent` já carrega (`conversation_id`, `outcome`, `agent`, `model`,
  `cost_usd`, `token_usage`, `latency_ms`, `handoff`, `tool_failures`) — todos ids, enums,
  números ou booleanos, nunca texto de conversa. `monitoring.tf` cria 5 `google_logging_metric`
  (`EXTRACT(jsonPayload.<campo>)`): `revenueflow_turn_cost_usd`, `revenueflow_turn_latency_ms`,
  `revenueflow_turns` (label `outcome`), `revenueflow_handoffs`, `revenueflow_tool_failures`.
  `request_count` / `response_time` / `error_rate` vêm das métricas **nativas**
  `run.googleapis.com/request_*` (zero código). `google_monitoring_dashboard` (JSON em
  `dashboards/revenueflow_ops.json`, carregado via `file()`) + 5 `google_monitoring_alert_policy`.
- **Logging estruturado stdlib, sem dependência (DA2).** O repo não tinha setup de logging —
  `_LOGGER.info` não emitia e `extra=` não era estruturado. `observability/logging_setup.py`
  traz um `JsonFormatter` (subclasse de `logging.Formatter`, ~25 linhas) que serializa cada
  record como JSON e **achata** os campos de `extra=` no objeto top-level (para o
  `EXTRACT(jsonPayload.*)` funcionar sem regex). `configure_logging()` é idempotente, seta o
  nível de `settings.log_level` (env `LOG_LEVEL`), chamado no `lifespan` e defensivamente no
  `run_subscriber`.
- **OTel → Cloud Trace como sink de produção da V1 (DA3).** `observability/otel_setup.py::configure_otel()`
  configura um `TracerProvider` global (`Resource` com `service.name`), `BatchSpanProcessor` +
  `CloudTraceSpanExporter`, com import **lazy** do SDK e do exporter (o módulo importa sem o extra
  `observability`) e **idempotente** (não re-seta se já houver um `TracerProvider` real). Chamado
  no `lifespan` **só** quando `settings.tracer_sink == "otel"`. `pyproject` extra `observability`
  += `opentelemetry-exporter-gcp-trace`; `Dockerfile` passa a instalar
  `.[events,llm,observability]`. `apis.tf` += `cloudtrace.googleapis.com` (+ `logging` +
  `monitoring`); `iam.tf` += `roles/cloudtrace.agent` (mínimo, ADR-008) na SA de runtime;
  `terraform.tfvars.example` → `tracer_sink = "otel"`.
- **`tool_failures` = spans `tool.*` que propagaram exceção (DA4).** `AuditTracer.span` marca
  `entry["error"] = True` no `except` antes de re-levantar; `flush` conta. Erro de tool que o nó
  **captura e não re-levanta** (padrão `{"error": "unavailable"}` do `recommendation_node`) **não**
  é contado na V1 — o tile do dashboard chama a métrica de "tool exceptions", e o follow-up é um
  `Span.mark_error()` na `Protocol` ou um `tracer.event("tool.error")` padronizado.
- **`v_ai_cost_per_revenue` via `CREATE OR REPLACE VIEW` com subquery de receita pré-agregada
  (DA6).** `migrations/0010_ai_cost_revenue.sql`: `audit_event` ⟕ `(quote ⋈ sales_order WHERE
  status='PAID')` agregado **por conversa antes do join**, para não multiplicar `so.total` pelo
  nº de turnos auditados. Colunas: `conversation_id, ai_cost_usd, revenue, orders, turns`.
- **`MODEL_PRICES` com os valores publicados do Vertex AI Gemini + comentário de proveniência
  (DA7).** Mantém a estrutura `dict[str, tuple[float, float]]` (input, output USD/1M tokens);
  o comentário do módulo passa a citar a fonte (cloud.google.com/vertex-ai/generative-ai/pricing)
  e a data de consulta, com nota de "revisar a cada mudança da tabela do Google". Nenhuma consulta
  de preço em runtime (ADR-009).
- **Alertas sempre criados; canal de email opcional via `count` (DA5).** `alert_email` é
  `variable` com `default = ""`; o `google_monitoring_notification_channel` só existe se
  preenchido; as 5 `alert_policy` são sempre criadas, com `notification_channels = []` até o email
  ser setado. Os 5 limiares são `variable` com default (`5xx > 2%`, `p95 > 3000ms`,
  `tool_failures > 10/h`, `custo > $1/h`, ausência de turno por `15min`), ajustáveis por tfvar sem
  deploy de código. Toda `variable` nova tem `default` — o job `plan` do `terraform.yml` só passa
  `project_id`/`region`/`image`.
- **Emenda ao ADR-045.** O ADR-045 escolheu Langfuse self-hosted atrás da porta `Tracer`. Esta
  fatia **não revoga** essa decisão: a impl `LangfuseTracer` continua válida e a troca é um tfvar
  (`tracer_sink = "langfuse"`). O que muda é o **sink que roda em produção na V1**: OTel → Cloud
  Trace, porque é gerenciado (sem provisioning) enquanto Langfuse self-hosted exige um Cloud Run +
  Postgres + secret. O cabeçalho do ADR-045 ganha uma nota apontando para cá.

## Alternativas consideradas
- **Cloud Run Job de push de custom metrics** (lê as views, escreve a Monitoring API) — +1 Job, +1
  Cloud Scheduler (nem existe ainda), +1 superfície de credencial, latência de N min. A SPEC-034
  pede "básico", não agregado exato.
- **Export de `audit_event` para BigQuery + dashboards BQ** — é literalmente a fatia ANALYTICS
  (PRD-015), pós-V1 explícito; traria BigQuery e custo recorrente para a V1.
- **Langfuse self-hosted agora** — hosting + Postgres + secret + custo recorrente; adiado
  repetidamente. A porta torna a troca trivial.
- **OTLP genérico para um collector** — precisaria do collector (mais um deploy); o exporter
  direto do Google não.
- **`SimpleSpanProcessor`** — exporta síncrono por span → entra no caminho do turno (fere
  SPEC-035).
- **`python-json-logger`** — 2ª dep nova para ~25 linhas de formatter stdlib.
- **`textPayload` + regex no `google_logging_metric`** — frágil; Google recomenda `jsonPayload`.
- **`Span.mark_error()` na `Protocol` agora** — toca os 3 sinks + `_BufferedSpan` + todo nó que
  chama tool; escopo grande para um contador.
- **Coluna `tool_failures` em `audit_event` (`0011`)** — a AUDIT_TRAIL acabou de estabelecer "1
  linha por turno"; a métrica vive bem só no log.
- **`sum(DISTINCT so.total)` direto no join** — errado se duas orders da mesma conversa tiverem o
  mesmo total.
- **`alert_email` obrigatória (sem default)** — quebra o `plan` do CI.
- **Alertas gated por `count` junto com o canal** — perde os alertas inteiros quando não há email.

## Motivo
O grosso da instrumentação (o `AuditEvent`) já existe (ADR-040/055) — falta **expor**. Log-based
metrics + métricas nativas do Cloud Run entregam as 7 métricas da SPEC-034 sem job, schedule ou
credencial. OTel → Cloud Trace dá o waterfall por-span em prod sem infra (serviço gerenciado),
complementando o `audit_event` (nível de turno) com o breakdown (nível de span). Tudo declarativo,
aplicado pelo `terraform.yml` que já existe. `MODEL_PRICES` reais tornam o KPI de custo (ADR-023)
defensável.

## Consequências
- +2 módulos (`logging_setup`, `otel_setup`); +1 migration (view); +1 `monitoring.tf` (5 log
  metrics + 1 dashboard + 5 alert policies + canal condicional) + `dashboards/revenueflow_ops.json`;
  +3 APIs; +1 IAM member; +6 `variable` (todas com default); +1 dependência
  (`opentelemetry-exporter-gcp-trace`, só no extra `observability`).
- Todo log do serviço passa a ser JSON (benefício além desta linha; em dev local fica menos
  legível — `LOG_FORMAT=text|json` é follow-up).
- `test_tracer.py::test_new_tracer_wraps_in_audit_by_default` e os testes de `AuditTracer` ganham
  asserts sobre a linha `audit.turn`; +2 arquivos de teste de unidade + 1 de integração (view) +
  1 de shape do Terraform.
- `TracerProvider` global é estado de processo — a fixture de `test_otel_setup.py` reseta.
- O caminho real (export p/ Cloud Trace) não tem CI — depende de `terraform plan` + os testes de
  unidade + verificação manual pós-deploy (ver spans no console).
- Alertas sem `alert_email` não notificam até o tfvar ser setado — pendência operacional (junto
  de "rodar a `0010`").
- `tool_failures` subconta falhas de tool que o nó trata graciosamente — documentado; follow-up é
  `Span.mark_error()` / `tracer.event("tool.error")`.
- Retenção/cardinalidade de log-based metrics — histórico longo é a fatia ANALYTICS.
- Ligar Langfuse self-hosted continua possível por tfvar (a porta não muda).

## Regra de revisão
Mudanças nesta decisão — em especial trocar o sink de produção, pôr a auditoria/o custo no
caminho síncrono da resposta, mover as métricas para um job de push, ou pôr o LLM na montagem da
linha `audit.turn` — exigem novo ADR ou superseding ADR.
