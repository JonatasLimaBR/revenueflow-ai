# ADR-055 — Audit Trail: `AuditTracer` envolve o sink + uma linha por turno via `flush()`

## Status
Accepted

## Contexto
A porta `Tracer` (`observability/tracer.py`) já instrumenta **tudo** que a SPEC-028 pede: cada nó
e cada tool abrem um `span`; cada chamada LLM é uma `generation` com `model`/`prompt_version` e,
no caminho real, `generation.update(usage=, cost_usd=)`; decisões viram `event`; o turno fecha com
`end(outcome=, policy_decision=, handoff=)`; `new_tracer(conversation_id, turn_id)` carrega a
correlação. **Nada disso é persistido no OLTP** — só vai para o sink de `tracer_sink` (`noop` por
default, `langfuse`, `otel`). Em produção não há como reconstruir um atendimento (PRD-013) nem
consultar "custo de IA por conversa" (ADR-023), e a tabela de auditoria da SPEC-028 não existe.

Restrições: auditoria **obrigatória para ações comerciais** (SPEC-028, ADR-022/040); não duplicar
a instrumentação; não somar latência ao caminho da resposta (SPEC-035); LLM não é fonte de verdade
(ADR-009 — a montagem da linha é determinística); PII minimizada (SPEC-031, ADR-032 — o `mask()`
do tracer já roda); a suíte roda só com `postgres:16`.

## Decisão

- **`AuditTracer` envolve o sink primário (DA1).** Implementa a `Protocol` `Tracer` inteira: cada
  `span` / `generation` / `event` / `end` é **encaminhado ao `primary`** (o sink de `tracer_sink`)
  **e** acumulado num buffer ordenado. `span` e `generation` cronometram com `time.perf_counter`;
  o wrapper de `Generation` captura `usage`/`cost_usd` no `update`; `end` guarda
  `outcome`/`policy_decision`/`handoff` e a latência do turno. Zero call site de instrumentação
  muda.
- **Uma linha `audit_event` por turno (DA2).** `0009_audit.sql` cria `audit_event` com **colunas
  planas** para os agregados (`agent, model, prompt_version, outcome, policy_decision, handoff,
  token_usage, cost_usd, latency_ms`) + `tools jsonb` (nomes de span `tool.*`) + `events jsonb`
  (buffer inteiro, para reconstrução). `audit_id = turn_id` (PK; único por turno via
  `envelope.event_id`) → `INSERT ... ON CONFLICT (audit_id) DO NOTHING` (idempotente). Índice em
  `conversation_id`. `0009` também cria `v_ai_cost_per_conversation` e `v_ai_cost_per_outcome`
  (KPIs do PRD-013 por SQL puro).
- **`flush()` na porta (DA3).** `Tracer` Protocol ganha `async def flush(self) -> None`;
  `NoopTracer` / `LangfuseTracer` / `OTelTracer` implementam como no-op. Só o `AuditTracer` faz
  trabalho: monta o `AuditEvent` do buffer e chama `services.audit.persist`. Chamado no `finally`
  de `process_event` / `process_approval_decided` / `scan`, **depois** do `_send_once` e do
  `end()` (o caminho de exceção também chama `end(outcome="error")`, então é auditado). O import
  de `services.audit` é **lazy dentro de `flush`** para quebrar o ciclo
  `observability → services → observability`.
- **`AuditEvent` em `domain/models.py` (DA3).** Como toda entidade do repo (`Handoff`,
  `Opportunity`, …); `domain` não importa nada da app, então `observability → domain` é acíclico.
- **`agent` = último span `node.*`, `latency_ms` até o `end` (DA4).** O `AuditTracer` captura o
  nome do último span `node.*` (sem o prefixo) como `agent` — uniforme entre
  `process_event`/`resume`/`scan`, sem o consumer precisar passar `result["current_agent"]`.
  `latency_ms` = `perf_counter` do `__init__` ao `end` — **não** inclui o `INSERT` (assíncrono,
  pós-resposta). Sem `lead_id` na linha nesta fatia (o `scan`/`resume` não têm; "custo por lead"
  é follow-up — a coluna entra sem migração de dados).
- **`audit_enabled = True` por default (DA5).** `new_tracer` monta o `primary` e, se
  `audit_enabled`, devolve `AuditTracer(primary, …)`; senão o `primary` cru. Ortogonal a
  `tracer_sink`. Desligável só para testes de unidade puros do tracer / degradação.
- **Rota `GET /internal/audit/{conversation_id}`** (Bearer — **reusa** `HANDOFF_API_TOKEN` via
  `settings.handoff_api_token`; escopos "ops read-only") → `services.audit.reconstruct` →
  `audit_repo.by_conversation` (ordenado por `created_at`).
- **`services.audit.persist` nunca propaga** — `try/except` → `_LOGGER.exception` com `trace_id`
  (SPEC-034). O turno já respondeu ao cliente.

## Alternativas consideradas
- **`audit.record(...)` explícito em cada tool / generation / nó** — duplica a instrumentação do
  `Tracer`, N writes por turno, cada ponto novo é um lugar a esquecer.
- **4º valor `postgres` para `tracer_sink`** (streaming por span) — N writes síncronos no caminho
  do turno (latência, SPEC-035), e vira **toggle** — a SPEC-028 quer auditoria obrigatória.
- **Só `events jsonb`, sem colunas planas** — todo KPI viraria `jsonb_path_query` (lento,
  ilegível).
- **Uma linha por span/generation** (tabela normalizada) — N writes/turno; reconstrução vira
  `JOIN` + `ORDER BY`.
- **`flush` só no `AuditTracer` + `getattr(t, "flush", None)` nos 3 call sites** — untyped, feio,
  fácil de esquecer num 4º call site.
- **`AuditEvent` em `observability/`** — `observability` viraria dono de uma entidade de domínio.
- **`AuditTracer.flush` chama `repositories.audit.record` direto** — perde a camada de
  `try/except`+log; e `repositories/__init__` pode arrastar `observability`.
- **`agent` = `result["current_agent"]` passado ao `flush`** — acopla o `flush` à assinatura do
  consumer; `scan`/`resume` não têm um `result` no mesmo formato.
- **`audit_enabled = False` por default** — arrisca prod sem auditoria por esquecimento de config;
  contra "obrigatório".

## Motivo
A instrumentação já existe (ADR-040) — o que falta é o destino. Envolver o sink é o menor delta:
nenhum `span`/`generation` novo, nenhum call site tocado. Uma linha por turno = 1 `INSERT` fora do
caminho crítico (a resposta já saiu). Colunas planas dão o KPI de custo do ADR-023 por SQL puro; o
`events jsonb` guarda a granularidade da reconstrução. `audit_enabled` on por default respeita
"obrigatório" da SPEC-028. O `mask()` do tracer roda antes do buffer, então a linha nunca guarda
PII crua.

## Consequências
- +1 tabela + 2 views + 1 migration; +1 dataclass; +1 repositório; +1 serviço; +1 router; +1
  método na porta `Tracer` (`flush`, no-op ×3); `AuditTracer` + 2 wrappers internos em
  `observability/tracer.py`.
- +1 `INSERT` por `message_received` processado + 1 por `approval_decided` + 1 por `scan` —
  **depois** da resposta, fora do P95.
- `test_tracer.py::test_new_tracer_defaults_to_noop` precisa mudar (`new_tracer` agora devolve
  `AuditTracer` por default) — 3ª vez que um teste de invariante em outro arquivo entra no build
  da fatia (enum de sessão / fronteira de tools / agora o tracer).
- `audit_event` cresce sem retenção — particionamento por data + TTL-sweep é fatia futura de
  escala.
- View "AI cost / revenue" (join `audit_event → quote → sales_order`) → OBSERVABILITY_OPS.
- `MODEL_PRICES` do `cost.py` continua placeholder — o `cost_usd` do audit é tão bom quanto ele;
  confirmar via `gcp-cli` MCP é follow-up.
- `agent` é `null` para `scan` (não abre `node.*`) — aceitável.
- Sem infra nova: a rota reusa `HANDOFF_API_TOKEN`. A `0009` roda pelo Job
  `revenueflow-api-migrate`.

## Regra de revisão
Mudanças nesta decisão — em especial pôr o LLM na montagem da linha, transformar a auditoria num
toggle não-obrigatório, ou mover a persistência para o caminho síncrono da resposta — exigem novo
ADR ou superseding ADR.
