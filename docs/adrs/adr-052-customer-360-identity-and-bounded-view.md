# ADR-052 — Customer 360: identidade determinística por telefone + visão comercial limitada tool-gated

## Status
Accepted

## Contexto
`services/identity.resolve(phone)` sempre devolveu `customer_id = None`: não há store de cliente,
`conversation_session.customer_id` nunca é preenchida, o ramo `if customer_id:` de
`recommendation_node` está morto, e `sim_customer_sales` / `sim_customer_pricing` (chaveados por
`customer_id`, sem telefone) são inalcançáveis a partir do inbound. `sim_customer_sales` também
não tem valor monetário, então `revenue_12m` / `average_ticket` (SPEC-017) não têm fonte.

Restrições: LLM não é fonte de verdade (ADR-009) — identidade e visão 360 determinísticas;
Customer 360 **não** vai inteiro ao LLM, só uma tool de contexto mínimo (ADR-033); least
privilege de tool por arquitetura (SPEC-024/025, ADR-008/037) — ampliar registry exige ADR;
dados simulados primeiro (ADR-028); `estimated_ltv` / `churn_score` fora enquanto não há
histórico para modelo (ADR-018); a suíte roda só com `postgres:16`.

## Decisão

- **Entidade `customer` + read-model `sim_customer_order`.** `migrations/0006_customer.sql` cria
  `customer (customer_id PK, phone UNIQUE, name, segment, created_at)` e
  `sim_customer_order (customer_id, order_id, total, ordered_at, items, PRIMARY KEY (customer_id, order_id))`.
  Sem `ALTER`, sem backfill; `CREATE TABLE IF NOT EXISTS`. Ambas semeadas (ADR-028): 3 clientes
  fixos com telefones `5511900000001..3`.
- **`resolve()` estende, assinatura preservada.** Consulta `customer.get_by_phone(phone)` (match
  exato) antes do lead: cliente conhecido → `(customer_id, None)`; senão → get-or-create de lead
  provisório → `(None, lead_id)` (byte-a-byte com o comportamento anterior). A gravação de
  `conversation_session.customer_id` fica no `worker/consume.py::process_event` (que conhece o
  `conversation_id`), via `session_repo.set_customer`, condicional a `customer_id is not None`.
- **`customer_360()` — agregação on-read determinística.** `repositories/customer.py::customer_360`
  é SQL puro: CTE `orders` = `sim_customer_order` **UNION ALL** `sales_order` (por `customer_ref`),
  janela de 365 dias; `orders_12m` / `revenue_12m` / `last_purchase` do agregado;
  `purchase_interval_days` via `lag() OVER (ORDER BY at)` (null com < 2 pedidos);
  `average_ticket` calculado em Python/`Decimal` (`"0"` quando não há pedidos);
  `preferred_products` = top-3 `product_id` por `sum(last_qty)` em `sim_customer_sales` (só o id);
  `open_quotes` = `quote` `SENT` por `customer_ref`. Retorno passa por `Customer360View` pydantic
  (`Decimal` → string, datas → ISO). Sem materialização.
- **Tool estreita, só no registry de recomendação.** `get_customer_360(customer_id)` entra em
  `RECOMMENDATION_TOOLS` / `RECOMMENDATION_TOOL_NAMES` **apenas** — nunca em `NEGOTIATION_*` /
  `CHECKOUT_*`. Devolve só o dict da `Customer360View` (nunca linhas cruas). No ramo
  `if customer_id:` de `recommendation_node`, **substitui** `get_customer_sales_context` (o 360 já
  traz `preferred_products`); a tool `get_customer_sales_context` continua registrada para o loop
  de tool-calling futuro.
- **Degradação graciosa.** Falha de `get_customer_360` no nó → `get_tracer().event` + log
  estruturado com `trace_id` (SPEC-034) + anexa `{"tool": "get_customer_360", "error": "unavailable"}`
  a `tool_results` (distinguível de "cliente desconhecido", que não anexa nada). O turno completa.

## Alternativas consideradas
- **Tabela-ponte `customer_phone` sobre os `sim_customer_*`, sem entidade `customer`** — sem
  âncora para `name` / `segment` / futuro LTV; `revenue_12m` continua sem fonte; não modela o
  cliente como pede o PRD-003.
- **`customer_id` na linha de `lead`** — conflita lead (pré-venda, SPEC-004) com cliente
  (pós-venda, SPEC-017); ciclos de vida distintos; o 360 fica sem entidade própria.
- **Semear `quote` + `sales_order` reais para o histórico** — arrasta o índice único parcial de
  `quote` e a FK `sales_order.quote_id`; seed frágil. `sim_customer_order` é um read-model limpo.
- **View / tabela materializada `customer_360`** — otimização sem necessidade no volume V1; mais
  migration e manutenção.
- **Uma query monolítica com todos os campos** — `preferred_products` e `open_quotes` vêm de
  tabelas diferentes; juntar tudo num `SELECT` piora legibilidade sem ganho.
- **`resolve(phone, conversation_id)` gravando a sessão dentro** — viola a assinatura congelada
  (DEFINE C7) e acopla identidade a sessão.
- **Manter as duas tools (`get_customer_sales_context` + `get_customer_360`) no nó** — 2
  round-trips, `preferred_products` duplicado em `tool_results`.
- **`get_customer_360` também em `NEGOTIATION_TOOLS`** — negociação já resolve por
  `sim_customer_pricing`; widening exige ADR próprio, contra ADR-033 "mínimo necessário".
- **Omitir a entrada de `tool_results` em falha** — indistinguível de "não é cliente"; o
  grounding não sabe que degradou.

## Motivo
O cliente vira entidade de primeira classe (PRD-003), com âncora para atributos e para as
próximas fatias (Opportunity Engine, LTV/churn). A visão 360 é execução determinística pura
(ADR-009), tool-gated no contexto mínimo (ADR-033), com a fronteira de permissão imposta por
arquitetura (a função `customer_360` não está no registry de nenhum outro agente). `resolve()`
mantém a assinatura, então `process_event` continua sendo o único ponto que orquestra
sessão + identidade. `sim_customer_order` dá números de demo não-vazios sem semear pares
`quote` + `sales_order`.

## Consequências
- +1 migration, +2 tabelas, +1 repositório, +1 tool, +1 schema pydantic, +1 dataclass de domínio.
- +3 queries no banco por turno de cliente conhecido (read-only, `read_connection`); trivial no
  volume simulado.
- `tests/security/test_tool_permissions.py::test_recommendation_tool_names_are_exact` e o set
  `ALLOWED["recommendation"]` **precisam** incluir o 5º nome — todo registry novo alcançável pelo
  grafo mexe nesse arquivo (lição do CHECKOUT).
- Datas absolutas no seed "envelhecem" — em 2027 o pedido de "~400 dias" de CUST-001 entra na
  janela. Follow-up: seed com datas relativas a `now()`. Não bloqueia a V1.
- `get_customer_sales_context` fica órfã no fluxo vivo (continua registrada para o tool-calling
  futuro; candidata a remoção se a fatia de LLM não a usar).
- Sem infra nova, sem secret novo. A `0006` roda pelo Cloud Run Job `revenueflow-api-migrate`.
- `estimated_ltv` / `churn_score` / `next_best_action` continuam fora — ML só depois de histórico
  (ADR-018); a NBA é a fatia OPPORTUNITY_ENGINE (SPEC-018).

## Regra de revisão
Mudanças nesta decisão — em especial ampliar o alcance de `get_customer_360` para outros
registries de tools, ou pôr o LLM no caminho de identidade / agregação do 360 — exigem novo ADR
ou superseding ADR.
