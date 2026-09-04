# ADR-057 — Orçamento de latência: timeout por dependência + teto duro no turno

## Status
Accepted

## Contexto
A SPEC-035 pede "P95 < 5s para fluxos simples", mas **nada no código impõe um limite de tempo**:

- `services/llm.py::_generate_with_retry` chama `client.aio.models.generate_content(...)` **sem
  timeout** — uma conexão Vertex pendurada trava o turno indefinidamente. `_is_transient` já
  **trata** `TimeoutError` se um ocorrer, mas ninguém **impõe** um.
- O `AsyncConnectionPool` de `repositories/db.py` não tem `statement_timeout`.
- `worker/consume.py` roda `get_graph().ainvoke(...)` (nos 2 consumidores) sem `asyncio.wait_for`
  — vários tool calls + LLM + retry empilham sem corte.
- Só o `httpx` do `whatsapp_outbound.py` é limitado.
- `opportunity`/`handoff`/`approval` têm índice **único parcial** (`WHERE status='OPEN'/'PENDING'`);
  `list_by_status(<outro status>) ORDER BY created_at` faz seq scan. `quote WHERE customer_ref = %s
  AND status = 'SENT'` (usado por `customer_360`/`checkout`) idem.

O `revenueflow_turn_latency_ms` + o alerta de p95 (OBSERVABILITY_OPS / ADR-056) são o **medidor**;
falta o lado do **enforcement**.

Restrições: LLM não é fonte de verdade (ADR-009 — timeout não muda a semântica); idempotência
(ADR-021 — o `processed_event.claim` é committado antes do turno); autonomia proporcional ao risco
(ADR-036 — turno preso degrada, não improvisa); observabilidade (SPEC-034/ADR-055 — falha vira
trace); nenhuma dependência nova; a suíte roda só com `postgres:16`.

## Decisão

- **Timeout por dependência + teto duro no `ainvoke` (DA1).** Três `asyncio.wait_for`:
  1. **Vertex** — cada `await call(client)` em `_generate_with_retry` embrulhado em
     `asyncio.wait_for(call(client), timeout=llm_call_timeout_s)` (**6.0s**). Um `TimeoutError`
     (== `asyncio.TimeoutError` em 3.12) continua sendo transitório via `_is_transient` → conta
     uma tentativa → retry; exaustão → `LLMError` → nó `handoff` (ADR-049, inalterado).
  2. **Postgres** — o `AsyncConnectionPool` da app nasce com
     `kwargs={"options": f"-c statement_timeout={db_statement_timeout_ms}"}` (**3000ms**). Estouro
     → `psycopg.errors.QueryCanceled` → `except Exception` do consumidor → re-raise → nack →
     redelivery.
  3. **Turno** — `result = await asyncio.wait_for(get_graph().ainvoke(...), timeout=turn_budget_s)`
     (**15.0s**) nos dois consumidores. Teto de **turno preso**, não de "turno lento".
  Os três são `Settings` (`LLM_CALL_TIMEOUT_S` / `DB_STATEMENT_TIMEOUT_MS` / `TURN_BUDGET_S`) —
  recalibráveis por env sem redeploy.
- **O alvo de 5s continua MEDIDO, não imposto (DA1).** `turn_budget_s` (15s) folgado ≠ alvo de
  P95 < 5s. O que mede o SLA é a métrica `revenueflow_turn_latency_ms` + o alerta
  `alert_p95_latency_ms` da OBSERVABILITY_OPS.
- **O caminho de `outcome="timeout"` acka e responde; nunca nack (DA2).** `except TimeoutError:`
  → `_send_once(<_SLOW_REPLY fixo>)` + `get_tracer().end(outcome="timeout")` + `return True`. O
  `processed_event.claim` já foi committado → a mensagem **não pode** ser reprocessada; a única
  saída correta é responder e ackar. O `finally` roda o `flush()` → grava `audit_event` com
  `outcome="timeout"` (aparece em `v_ai_cost_per_outcome` e no dashboard sem migração).
  `record_turn` (intent/agent) é pulado. O turno morto deixa o checkpoint resumível → a próxima
  mensagem cai no guard `snapshot.next` que já existe.
- **`statement_timeout` via `kwargs={"options": ...}`, não `configure=` (DA3).** Uma linha, sem
  round-trip por checkout de conexão. **Não** cobre o pool do checkpointer LangGraph
  (`AsyncPostgresSaver.from_conn_string`) — o `turn_budget_s` (`wait_for` externo) é o backstop.
- **`llm_call_timeout_s = 6.0` (não 8.0) (DA4).** Com 6s/tentativa e `llm_max_retries=2`, ~2.2
  tentativas cabem dentro de `turn_budget_s=15` — o retry e o teto do turno coexistem sem um
  anular o outro. Um `gemini-2.5-flash` normal responde em 1–3s; 6s já é cauda longa.
- **4 índices, `IF NOT EXISTS`, sem `CONCURRENTLY` (DA5).** `0011_perf_indexes.sql`:
  `opportunity (status, created_at DESC)`, `handoff (status, created_at DESC)`,
  `approval (status, created_at)`, `quote (customer_ref) WHERE status = 'SENT'`. As tabelas têm
  dezenas de linhas na V1 → lock de milissegundos, e o Job de migração roda fora do tráfego.
  Corretos-por-design; sem impacto de performance mensurável **agora**.
- **`alert_p95_latency_ms` fica em 3000ms como early-warning (DA6).** Metade do alvo de 5s —
  "p95 subindo, olhe agora", não "estourou o SLA". Alinhar ao teto (15s) só avisaria quando
  turnos já estão sendo mortos.
- **`process_approval_decided` no timeout = simetria com `process_event` (DA7).** Mesmo
  `_reply_timeout` (ack + `_SLOW_REPLY` + `end("timeout")`). O `claim(kind="resume")` bloqueia a
  redelivery do mesmo jeito; o cliente espera o desfecho da aprovação.

## Alternativas consideradas
- **Só timeout por dependência** (Abordagem B) — não garante o teto do **turno**, que é o que a
  SPEC-035 pede; a soma de sub-timeouts (2 retries a 6s + N queries a 3s) ainda estoura qualquer
  P95.
- **+ circuit breaker de Vertex** (Abordagem C) — estado compartilhado entre turnos num serviço
  horizontal (teria que ir pro Postgres/Redis); os alertas de outage (5xx, sem-turnos) + o
  handoff-on-LLM-failure já cobrem.
- **`turn_budget_s` = alvo de P95 (5s)** — cortaria turnos legítimos-lentos para pegar a cauda;
  degradar UX para medir.
- **`raise` (nack) no timeout do turno** — a redelivery é bloqueada pelo `claim`; o cliente fica
  **sem resposta**.
- **Liberar o `claim` no timeout e nack** — janela de duplo-processamento (a redelivery re-roda
  o turno inteiro; a idempotência do repo é por-operação, não cobre "meio turno").
- **`configure=async def` para o `statement_timeout`** — mais código, +1 round-trip por conexão.
- **`llm_call_timeout_s=8`, `turn_budget_s=20`** — 20s é longe demais do alvo de 5s.
- **`CONCURRENTLY` nos índices** — exige rodar fora de transação; muda o runner de migração por um
  ganho nulo na V1 (tabelas minúsculas).
- **`alert_p95_latency_ms` subindo para 5000/15000** — avisa tarde demais para prevenir.
- **Nack no timeout do `process_approval_decided`** — mesmo problema de `claim` + duplo-processamento.

## Motivo
O `wait_for` externo no `ainvoke` é a **única** coisa que dá um teto real ao turno (SPEC-035);
per-dependência sozinho não limita a soma. Encaixa nos pontos de extensão que já existem (o loop
de retry, o caminho de `handoff`, o `_send_once`, o guard de `snapshot.next`). Zero dependência
nova. `outcome="timeout"` cai na linha `audit.turn` sem mudança de schema. Os índices previnem o
"seq scan cliff" quando o volume crescer.

## Consequências
- +3 `Settings`; +1 `asyncio.wait_for` no `_generate_with_retry`; +`kwargs` no
  `AsyncConnectionPool`; +`_SLOW_REPLY` + `_reply_timeout` + `except TimeoutError` (×2) em
  `worker/consume.py`; +1 migration (4 índices).
- `outcome="timeout"` é o único valor novo de `outcome` — sem migração de `audit_event`.
- Uma resposta Vertex legítima de 7s vira `TimeoutError` → retry/handoff. Aceitável: 7s num
  "fluxo simples" já viola a SPEC-035.
- Nack-loop se uma query **sempre** estoura o `statement_timeout` → Pub/Sub max delivery attempts
  → DLQ/descarte. Visível nos alertas 5xx / sem-turnos.
- O pool do checkpointer não tem `statement_timeout` — follow-up (passar `kwargs` ao
  `AsyncPostgresSaver` também).
- Os índices são no-op de performance mensurável na V1 — corretos-por-design.
- `conversation_session.intent`/`agent` não refletem um turno que estourou (o `audit_event` é a
  fonte de reconstrução).
- Follow-ups: `turn_budget_s` por-fase (C2), pool/timeout maior para o Job de `scan` (C1),
  `statement_timeout` no checkpointer (A4), métrica `revenueflow_turn_timeouts` dedicada (C3).

## Regra de revisão
Mudanças nesta decisão — em especial remover o teto do turno, transformar o timeout num nack que
reprocessa meio turno, pôr o LLM na resposta de `outcome="timeout"`, ou apertar `turn_budget_s`
para o valor do alvo de P95 — exigem novo ADR ou superseding ADR.
