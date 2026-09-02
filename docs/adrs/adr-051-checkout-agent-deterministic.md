# ADR-051 — Checkout Agent como nó determinístico + `CHECKOUT_TOOLS`; confirmação determinística

## Status
Accepted

## Contexto
O fluxo inbound leva o cliente até preço, proposta de desconto e retomada de aprovação, mas não
fecha venda: não há `Quote`, `Order` nem `Payment` no domínio, e `create_quote` /
`create_order` / `create_payment_sandbox` estão explicitamente proibidas em todos os registries
de tools (`tools/registry.py`) — ampliar exige ADR (ADR-037). A fatia CHECKOUT entrega o
vertical, tudo simulado (ADR-029: pagamento só sandbox; ADR-030: documento comercial simulado).

Restrições: LLM não é system of record para pedido/preço/pagamento (ADR-009); operações
financeiras determinísticas (ADR-025); confirmação é regra de negócio determinística
(SPEC-014); criação de pedido idempotente + revalidação de estoque (SPEC-015); least privilege
por arquitetura (SPEC-024/025, ADR-037); a suíte roda só com `postgres:16`.

## Decisão

- **Checkout Agent = nó determinístico.** `checkout_node` (`agents/checkout.py`), no molde de
  `negotiation_node` / `apply_decision_node` — **não** um loop de tool-calling de LLM. Ele chama
  `create_quote` / `create_order` / `create_payment_sandbox` de um registry novo `CHECKOUT_TOOLS`
  e escreve a própria `reply` por template. `checkout_node`, `services/checkout.py` e
  `tools/checkout.py` **não importam `services.llm`**.
- **Fronteira de permissão isolada.** As três tools vivem **só** em `CHECKOUT_TOOLS`; nenhuma
  entra em `RECOMMENDATION_TOOLS` / `NEGOTIATION_TOOLS`. Um teste falha se a interseção deixar
  de ser vazia. `graph_tool_names` passa a incluir `CHECKOUT_TOOL_NAMES`.
- **Gate de confirmação = estado + matcher puro.** `supervisor_node` lê
  `repositories.checkout.get_open_quote(conversation_id)` e devolve `{"open_quote_id": <id|None>}`.
  `route_from_supervisor`: `open_quote_id` presente → nó `checkout` (pula
  recommendation/negotiation). `services.checkout.is_explicit_confirmation(text)` é uma **função
  pura** (normaliza NFKD, lista fechada de frases de fechamento, rejeita ambíguas e `"sim"`
  isolado). Sem `interrupt()`, sem `Intent` nova, sem coluna de sessão — o `quote` `SENT` é a
  fonte de verdade.
- **Roteamento.** `CHECKOUT_INTENTS = {ORDER_REQUEST}`. `ORDER_REQUEST` atravessa
  `recommendation` (resolve produto) → `negotiation` (resolve preço/alçada; desconto fora da
  alçada usa o `await_approval` / `apply_decision` da fatia APPROVAL_RESUME) → `checkout_node`
  cria o `Quote(status=SENT)` do estado resolvido (`price_quote`, `checkout_discount`,
  `requested_quantity`, `product_id`). `route_after_apply_decision`: `intent == ORDER_REQUEST` e
  `final_outcome ∈ {approved, overridden}` → `checkout`; senão `END`.
- **Idempotência + estoque (SPEC-015).** `sales_order.quote_id UNIQUE`;
  `INSERT ... ON CONFLICT (quote_id) DO NOTHING` + read-back — reconfirmar o mesmo quote devolve
  a `Order` existente. Antes do insert, `create_order` chama `get_inventory(product_id,
  quantity)` (a mesma tool read-only); `fulfillable == false` → **não** cria; `Quote` → `EXPIRED`;
  a `reply` cita `available`.
- **Payment sandbox (SPEC-016).** `create_payment_sandbox(order_id, amount)` é um fake que sempre
  aprova; a tabela `payment` só tem `payment_id/order_id/amount/status` — **nenhum** dado de
  cartão/PII. `Order` → `PAID`; `Quote` → `ACCEPTED`.
- **Schema.** `migrations/0005_checkout.sql`: `quote`, `sales_order` (`order` é reservada),
  `payment`; `items` como `jsonb` (lista de 1 elemento — forward-compat com carrinho); índice
  único **parcial** `quote (conversation_id) WHERE status = 'SENT'` (um quote aberto por conversa,
  imposto pelo banco).
- **Sem janela de escape nesta fatia.** Enquanto há quote `SENT` não-expirado, **todo** turno vai
  pro `checkout_node` (repergunta). Uma pergunta não-relacionada recebe a repergunta; o quote
  expira naturalmente. A janela de escape é fatia futura.

## Alternativas consideradas
- **`Intent.ORDER_CONFIRM` classificado pelo LLM** — joga "linguagem ambígua" no modelo, contra
  a SPEC-014; mistura checkout no prompt de intent.
- **Checkout Agent como loop de LLM (tool-calling)** — coloca o LLM no caminho de order/payment,
  contra ADR-009/025.
- **Ramo de checkout dentro do `negotiation_node`** — sobrecarrega um nó com dois trabalhos (o
  anti-padrão rejeitado em APPROVAL_RESUME).
- **`interrupt()` após o quote** — semântica de decisão de outro ator, assíncrona (ADR-039); aqui
  é o mesmo cliente no turno seguinte.
- **Coluna `conversation_session.pending_quote_id`** — duplica o que o `quote` já sabe; mais um
  lugar pra ficar inconsistente.
- **Idempotência por `(conversation_id, turn_id)`** — deixa uma segunda "sim, pode fechar" criar
  uma segunda order; `quote_id` é o semântico ("um quote → no máx. uma order").
- **Manter o `Quote` `SENT` no estoque insuficiente** — o cliente ficaria preso na repergunta sem
  forma de progredir sem mudar a quantidade (que o quote não suporta).
- **Colunas planas em vez de `items` jsonb** — exigiria migration quando o carrinho multi-item
  chegar.
- **Janela de escape agora** — reintroduz o julgamento que a SPEC-014 quer determinístico e
  multiplica os caminhos; YAGNI para o piloto B2B.

## Motivo
O padrão do repo é "LLM interpreta; Policy decide; API executa" — criação de pedido/pagamento é
execução pura, e `negotiation_node` já prova o padrão de nó determinístico. O registry isolado é
a fronteira de permissão por arquitetura (ADR-037): a função `create_order` simplesmente não está
na lista dos outros agentes. Ler `get_open_quote` no `supervisor` mantém o roteamento como
função síncrona. Reusar recommendation + negotiation + o gate de aprovação compõe de graça.

## Consequências
- +1 nó no grafo, +1 módulo de tools, +1 registry, +1 par repo/serviço, 3 entidades de domínio,
  1 migration. O `checkout_node` tem 4 desfechos (quoted / confirm_reprompt / ordered /
  out_of_stock) — coberto com testes parametrizados.
- +1 leitura no banco por turno (`get_open_quote`, indexada por `conversation_id`).
- UX pobre se o cliente fizer perguntas depois de receber o quote (sem janela de escape).
  Documentado; próxima fatia de checkout.
- Cliente que quer "ajustar a quantidade" após estoque insuficiente precisa recomeçar.
- Sem nova infra, sem novo secret. A `0005` roda pelo Cloud Run Job `revenueflow-api-migrate`.
- Quando o Recommendation Agent virar LLM (fatia `WHATSAPP_INBOUND_RECOMMENDATION_LLM`), o
  checkout continua determinístico.

## Regra de revisão
Mudanças nesta decisão — em especial ampliar `CHECKOUT_TOOLS` ou pôr o LLM no caminho de
order/payment — exigem novo ADR ou superseding ADR.
