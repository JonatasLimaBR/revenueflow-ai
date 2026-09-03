# ADR-054 — Human Handoff: gatilhos determinísticos + entidade + contexto estruturado

## Status
Accepted

## Contexto
`Intent.HUMAN_SUPPORT` existe no enum mas **não tem rota no grafo** — cai em `respond` e o
cliente que pede um atendente recebe uma resposta de LLM. O `handoff_node` atual só é alcançado
em **falha de LLM**, devolve uma frase fixa, **não persiste nada** e **não monta contexto**.
SPEC-026 quer transferência determinística em condições de risco ou pedido explícito, com o
motivo registrado; SPEC-027 quer um resumo estruturado entregue ao humano sem exigir leitura
integral da conversa.

Restrições: LLM não é fonte de verdade (ADR-009) — a decisão de transferência e o resumo são
determinísticos; ações de alto impacto exigem humano (ADR-013); autonomia proporcional ao risco
(ADR-036); idempotência (ADR-021); a suíte roda só com `postgres:16`; o turno **não** retoma
(sem `interrupt()`).

## Decisão

- **3 gatilhos determinísticos via `policies/handoff_policy.py` (DA1).** `should_handoff(*, intent,
  confidence, resolved_total, min_confidence, high_value_threshold) -> HandoffReason | None` é uma
  função **pura** (molde de `pricing_policy.evaluate()`), precedência fixa: `explicit_request`
  (`intent == HUMAN_SUPPORT`) > `high_value_order` (`resolved_total > high_value_threshold`) >
  `low_confidence` (`confidence < min_confidence`) > `None`. `repeated_errors` e
  `critical_complaint` ficam de fora (contador de turnos com erro / corpus de frases — fatias
  futuras); `out_of_policy` já é o fluxo de `Approval`.
- **Entidade `handoff` + índice único parcial (DA2).** `0008_handoff.sql` cria
  `handoff (handoff_id PK, conversation_id, reason text NOT NULL, context jsonb NOT NULL, status,
  created_at)` + `CREATE UNIQUE INDEX ... ON handoff (conversation_id) WHERE status = 'PENDING'`.
  `create` = `INSERT ... ON CONFLICT DO NOTHING` + read-back — mesmo padrão do
  `quote_one_open_per_conversation` (`0005`) e do `opportunity_one_open_per_signal` (`0007`).
  `context jsonb NOT NULL` impõe a explicabilidade da SPEC-027 no schema.
- **`build_context` determinístico (DA3).** `services/handoff.py::build_context(state)` devolve as
  8 chaves da SPEC-027 (`conversation_summary` por template, `customer`, `intent`, `products`,
  `quote`, `objections`, `reason`, `next_best_action`) — de `state` + 1 query `customer`
  (`{customer_id, name, segment}` — **não** o `customer_360`, para minimizar PII persistida,
  SPEC-031) + 1 query da `opportunity` OPEN do cliente (`recommended_action` → `next_best_action`,
  reusa OPPORTUNITY_ENGINE). Sem LLM (ADR-009).
- **Módulo `agents/handoff.py` novo (DA4).** `_HANDOFF_REPLY` + `to_handoff(reason)` (builder puro
  do dict) + `handoff_node` (agora com I/O: `build_context` + `create` + `update_status`). Vive
  apart de `graph.py` porque `graph.py` importa os nós — pôr o builder lá criaria o ciclo
  `graph → negotiation → graph`. `agents/handoff.py` só importa `services`/`repositories`/`domain`.
- **LLM-failure handoff também persiste (DA4, OQ5).** `handoff_node` **sempre** cria o `Handoff` e
  marca a sessão `HUMAN_HANDOFF`, para os 5 `HandoffReason` (`explicit_request` / `low_confidence`
  / `high_value_order` / `intent` / `respond`). Uniforme; o atendente vê também os casos em que o
  modelo caiu.
- **Rota interna + secret próprio (DA5).** `api/handoffs.py` — `GET /internal/handoffs?status=PENDING`
  + `POST /internal/handoffs/{id}` (transição condicional `PENDING → RESOLVED`), Bearer
  `HANDOFF_API_TOKEN` (`503` sem token, `401` sem/errado) — molde de `api/approvals.py`. O secret
  é **novo** (`revenueflow-handoff-api-token`), Terraform-generated via `random_password.handoff_token`
  (molde do `approval_token`) — escopos internos isolados (o approval concede desconto; o handoff
  expõe a conversa).
- **Guard no consumer (DA5).** `worker/consume.py::process_event`: `session.status ==
  HUMAN_HANDOFF` → envia uma frase fixa (`dispatch.reserve`) e retorna **sem** `ainvoke`. Molde do
  guard `_HELD_FOR_APPROVAL`.
- **`high_value_order` no `negotiation_node` (DA6, OQ1).** A checagem `customer_price * qty >
  handoff_high_value_threshold` fica logo após `get_price`, antes de qualquer branch e do
  `checkout_node` — nenhum `Quote` é criado. Fallback de contexto mínimo `{reason, intent}` em
  falha de `build_context` (OQ4); id inexistente na rota → `200` no-op (OQ3).

## Alternativas consideradas
- **Handoff como `Intent` classificado + `respond` escreve a mensagem** — joga a decisão de
  transferência no modelo (contra SPEC-026 "determinístico" e ADR-009), sem contexto nem
  persistência.
- **Evento `handoff_requested` + consumer** (como o approval) — o APPROVAL_RESUME usou evento
  porque **precisava retomar o grafo**; aqui o turno termina no handoff.
- **`context text`** em vez de `jsonb` — perde a estrutura das 8 chaves da SPEC-027.
- **PK composta `(conversation_id, status)`** — impede segundo handoff histórico na mesma conversa.
- **`build_context.customer` = `customer_360` completo** — traz `revenue_12m` / histórico ao
  `context` persistido (mais PII) sem o handoff precisar disso.
- **`conversation_summary` por LLM** — ADR-009; e adiciona uma chamada de modelo no caminho onde
  o modelo pode já estar falhando.
- **`to_handoff` em `graph.py`** — ciclo de import com `negotiation.py`.
- **Reusar `APPROVAL_API_TOKEN`** — acopla dois escopos internos num token só.
- **LLM-failure handoff continua sem persistir** — o atendente não veria os casos de falha de
  modelo, e o guard do consumer não dispararia.
- **Check de alto valor num nó novo / no `checkout_node`** — nó/aresta extra, ou o `Quote` já
  teria sido criado.

## Motivo
O `handoff_node` já era o destino de transferência; a fatia dá a ele o trabalho que faltava
(decidir por regra, montar contexto, persistir). Regras puras em `policies/` = testáveis sem
banco (3ª vez que o molde `pricing_policy` paga). O índice único parcial faz o banco impor
idempotência. Persistir também os handoffs de falha de LLM significa que **toda** transferência
vira um `Handoff` listável — o operador não perde caso nenhum. O turno termina no nó (sem
`interrupt`): o humano assume, devolver o controle ao bot é outra semântica.

## Consequências
- +1 tabela, +1 migration, +1 policy, +1 repositório, +1 serviço, +1 módulo em `agents/`, +1
  router, +1 secret. `graph.py` perde `_to_handoff`/`handoff_node` (movidos para `agents/handoff.py`).
- +1 leitura de sessão por turno (o guard); +2 queries no `build_context` (só quando há handoff).
- 0 chamadas LLM no caminho de handoff.
- Uma conversa em `HUMAN_HANDOFF` fica assim **até o atendente resolver** — sem timeout automático
  nesta fatia (um TTL-sweep é fatia futura, como o de `Approval`).
- `conversation_summary` é de 1 turno (não usa o checkpoint multi-turno).
- `handoff_high_value_threshold = 50000` é placeholder para o catálogo simulado — é config.
- Sem notificação ativa ao atendente (Slack/email) — a rota `GET` é o canal; follow-up.
- Sem infra nova além do secret. A `0008` roda pelo `revenueflow-api-migrate`.

## Regra de revisão
Mudanças nesta decisão — em especial pôr o LLM na decisão de transferência ou no
`conversation_summary`, o Opportunity Engine/handoff disparar contato ativo, ou o bot retomar a
conversa após `RESOLVED` — exigem novo ADR ou superseding ADR.
