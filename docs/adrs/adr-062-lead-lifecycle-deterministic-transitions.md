# ADR-062 — LEAD_LIFECYCLE: transições determinísticas de status + promoção lead→customer

## Status
Accepted

## Contexto
Ao escopar o domínio Lead 360 do PRD-015 (fatia ANALYTICS_360), uma varredura no código mostrou
que `LeadStatus` nunca transiciona além de `NEW` — `QUALIFYING`/`QUALIFIED`/`PROPOSAL`/`WON`/`LOST`
existem no enum, mas nada os define. Pior: mesmo um lead cujo pedido é pago (`checkout_node`
retorna `final_outcome="ordered"`) nunca vira uma linha em `customer` — na próxima conversa,
`identity.resolve` o trata como lead de novo, sem histórico via CUSTOMER_360. Reportar um funil
vazio seria pior que não reportar nada; o usuário confirmou construir a transição real.

## Decisão

- **Regra pura e monotônica, mesmo molde de `handoff_policy`/`opportunity_policy` (ADR-009,
  ADR-017).** `policies/lead_policy.py::advance(current, *, intent, final_outcome) -> LeadStatus`
  — sem I/O, sem LLM. Precedência: `final_outcome=="ordered"` → `WON`;
  `final_outcome=="quoted"` → `PROPOSAL`; `intent ∈ {NEGOTIATION, QUOTE_REQUEST}` → `QUALIFIED`;
  `intent ∈ {PRODUCT_SEARCH, RECOMMENDATION, STOCK_REQUEST, PRICE_REQUEST}` → `QUALIFYING`; senão
  sem mudança. `WON`/`LOST` são terminais — a função nunca os move.
- **Avanço síncrono no turno; `LOST` é um sweep batch.** `advance_from_turn` roda em
  `worker/consume.py` logo após o `ainvoke` bem-sucedido — é barato (1 leitura + 1 update na mesma
  transação, sem I/O externo). `LOST` (ausência de atividade) é uma condição que só um batch pode
  observar — `services/lead_lifecycle.py::sweep_stale()`, mesmo molde de `opportunity.scan()`,
  via Cloud Run Job `revenueflow-lead-sweep` (espelha os 3 Jobs batch existentes).
- **Sem migração — reusa `conversation_session.last_interaction`.** `stale_candidates` faz um
  `LEFT JOIN` por telefone em vez de adicionar uma coluna `updated_at` em `lead`; o dado já existe
  e já é atualizado a cada turno (`session_repo.touch`).
- **Promoção lead→customer é parte da transição `WON`, não uma fatia separada.** Quando
  `advance_from_turn` calcula `WON`, cria um `Customer` real (`customer_id` novo, `phone` do lead)
  via `customer_repo.create` — idempotente pelo `ON CONFLICT (phone) DO NOTHING` já existente.
  Falha na promoção é logada e isolada (o `set_status` para `WON` já ocorreu; o turno já respondeu
  ao cliente — a promoção é best-effort, não bloqueia a resposta).

## Fora de escopo

- CRM/UI de gestão de lead — não pedido.
- Reabertura manual de um `LOST` — usa o `set_status` já existente, sem rota nova.
- Cloud Scheduler para o sweep — mesma decisão adiada das 3 fatias batch anteriores.
- Métricas/dashboard do funil de lead — é a fatia ANALYTICS_360 (Lead 360), que consome os dados
  que esta fatia passa a gerar.
- Qualquer LLM na decisão de transição — 100% regra determinística (ADR-009).

## Alternativas consideradas

- **Rank contínuo sem checar `current in (WON, LOST)` primeiro** — `LOST` (rank 4) poderia em
  tese "avançar" para `WON` (também rank 4) dependendo da ordem dos `if`; o guard explícito de
  terminalidade remove a ambiguidade.
- **Coluna `updated_at` nova em `lead`** — reusar `conversation_session.last_interaction` via
  join evita migração e mantém uma única fonte de "última atividade" por telefone.
- **Promover para `Customer` como uma fatia própria, depois da transição `WON`** — separaria uma
  decisão de negócio (quando alguém vira cliente) do sinal que a determina (pedido pago);
  manter as duas juntas evita um estado intermediário "`WON` mas ainda não é Customer".

## Motivo
O funil de Lead 360 do PRD-015 só tem valor se o dado for real. Construir a transição
determinística agora — no mesmo padrão de regra pura + batch já estabelecido em 3 fatias
anteriores — fecha a lacuna sem inventar um mecanismo novo, e sem migração.

## Consequências
- +1 policy, +3 funções de repositório, +1 serviço, +1 chamada em `worker/consume.py`, +1 script,
  +1 Cloud Run Job, +ADR-062. Sem migração, sem dependência nova, sem PII nova exposta (a
  promoção só copia o telefone já existente do lead).
- Um lead cujo status muda para `WON` mas cuja promoção falha (erro transitório de banco) fica
  `WON` sem `Customer` correspondente até o próximo turno tentar de novo — aceitável (best-effort,
  logado, não bloqueia a resposta ao cliente).
- `lead_stale_days=30` é um valor inicial sem calibração por dados reais — ajustável por env sem
  redeploy.

## Regra de revisão
Mudanças nesta decisão — em especial inverter a precedência outcome/intent, ou promover pra
`Customer` fora da transição `WON` — exigem novo ADR ou superseding ADR.
