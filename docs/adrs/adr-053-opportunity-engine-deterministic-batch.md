# ADR-053 — Opportunity Engine determinístico: scan em batch + regras puras + entidade

## Status
Accepted

## Contexto
O RevenueFlow é 100% reativo — só age quando o cliente escreve. PRD-010 quer detectar
**automaticamente** oportunidades a partir do histórico (recompra atrasada, proposta parada). Não
há entidade `opportunity`, nenhuma regra de detecção, e o `recommended_action` / `next_best_action`
que a SPEC-018 exige (e o CUSTOMER_360 adiou) não é produzido.

Restrições: ADR-019 manda **separar detecção de oportunidade da conversa**; SPEC-019 diz "gerar
opportunity, **não** mensagem"; SPEC-022 e ADR-020 põem o contato ativo atrás de um policy gate
(fatia OUTBOUND, não esta); SPEC-021 exige `reason` + `evidence` obrigatórios; ADR-018 proíbe ML
na V1; ADR-009 mantém o LLM fora da fonte de verdade; a suíte roda só com `postgres:16`.

## Decisão

- **Scan em batch, fora do grafo (DA1).** `services/opportunity.py::scan(now=None)` roda por
  `scripts/detect_opportunities.py` num Cloud Run Job (`revenueflow-opportunity-scan`). **Nenhum**
  nó no grafo, nenhuma aresta, nenhum `import` de `revenueflow.agents.*` nem
  `revenueflow.adapters`. O `scan()` abre o próprio `unit_of_work` e o próprio tracer
  (`trace_id` por execução, SPEC-034).
- **Entidade `opportunity` + índice único parcial (DA2).** `0007_opportunity.sql` cria
  `opportunity (opportunity_id PK, customer_id, opportunity_type, product, estimated_revenue,
  probability, reason text NOT NULL, evidence jsonb NOT NULL, recommended_action text NOT NULL,
  status, created_at)` + `CREATE UNIQUE INDEX ... ON opportunity (customer_id, opportunity_type,
  product) WHERE status = 'OPEN'`. `upsert_open` = `INSERT ... ON CONFLICT DO NOTHING` + read-back
  da OPEN correspondente (`product IS NOT DISTINCT FROM`). Mesmo padrão do
  `quote_one_open_per_conversation` (`0005`). `evidence jsonb NOT NULL` impõe a explicabilidade da
  SPEC-021 no schema. PK só em `opportunity_id` (não composta) preserva histórico:
  uma `CONVERTED`/`DISMISSED` antiga + uma `OPEN` nova do mesmo sinal coexistem.
- **Duas regras puras (DA3).** `policies/opportunity_policy.py`, molde de `pricing_policy.evaluate()`:
  `replenishment(signal, *, now, threshold)` dispara sse
  `days_since_last_purchase > average_purchase_interval * threshold`;
  `quote_recovery(signal, *, now, limit_hours)` dispara sse `status == 'SENT'` **e**
  `age > limit_hours` **e** `has_order is False`. `now` é **parâmetro** (sem `datetime.now()`
  interno) → teste determinístico. Sem I/O, sem `services.llm`.
- **`probability` constante, `estimated_revenue` derivado (DA3, ADR-018).** REPLENISHMENT →
  `probability = 0.35`, `estimated_revenue = average_ticket`; QUOTE_RECOVERY → `probability = 0.45`,
  `estimated_revenue = quote.total`. Os `probability` são **placeholders documentados** até haver
  dados para calibrar — sem modelo, sem falso ganho de precisão.
- **`reason` + `evidence` (DA4).** `reason` é uma f-string interpolada na regra com os números
  formatados; `evidence` é um `dict` com os mesmos números estruturados. Sem sistema de template.
- **Queries de candidatos em `repositories/opportunity.py` (DA4, OQ1).** `replenishment_candidates`
  = scan de todos os clientes com `HAVING count(*) >= 2` na janela de 365d (`sim_customer_order` ∪
  `sales_order`), `lag()` para o intervalo médio, subquery correlacionada em `sim_customer_sales`
  para o produto habitual (`product` = top `sum(last_qty)`, OQ2). `stale_quote_candidates` =
  `quote LEFT JOIN sales_order ... IS NULL WHERE status='SENT'` (o filtro de idade fica na regra,
  porque `now` é injetável).
- **Só Cloud Run Job, sem Cloud Scheduler (DA5).** `infra/terraform/opportunity_job.tf` cria só o
  `google_cloud_run_v2_job`, espelhando `migrate_job.tf`. O cron diário é follow-up documentado.
  `terraform.yml` já dispara em `infra/terraform/**` (OQ5).
- **`scan()` só detecta (DA6, OQ4).** Não faz transição de ciclo de vida: uma `OPEN` cujo sinal
  sumiu (quote virou order) fica `OPEN` até alguém fechá-la; `set_status` existe para uso manual /
  fatia futura de rastreio de conversão. O loop de `scan()` é resiliente por candidato
  (`try/except` → `errors += 1`, segue).

## Alternativas consideradas
- **Regra dentro do `recommendation_node`** — acopla detecção à conversa (viola ADR-019), só vê
  quem escreveu, não persiste com ciclo de vida.
- **Detecção dirigida por evento** (agendar checagem após cada `quote`/`order`) — precisa de Cloud
  Tasks / delay-queue que não existe; replenishment é a *ausência* de compra, não tem evento.
- **`evidence` como `text`** — perde a estrutura; SPEC-021 fala em "evidence", não "nota".
- **PK composta `(customer_id, type, product)`** — impede histórico de oportunidades do mesmo sinal.
- **`datetime.now()` dentro da regra** — não-testável (a fatia APPROVAL_RESUME já ensinou "nó
  re-entrante não tem relógio próprio").
- **`probability` calculado** — ML disfarçado sem dados (ADR-018).
- **Job + Cloud Scheduler diário agora** — +3-4 recursos de IaC (`google_cloud_scheduler_job`,
  API do Scheduler, SA invoker + binding) no apply automático do merge.
- **`scan()` marca `CONVERTED` quando o sinal some** — assume "sinal sumiu == convertido", nem
  sempre verdade; e não há evento de conversão confiável ainda.
- **Estender `repositories/customer.py` com a query de candidatos** — mistura "visão de 1 cliente"
  com "scan de todos"; dá duas responsabilidades ao módulo.

## Motivo
O padrão do repo é "LLM interpreta; Policy decide; API/entrypoint executa" — detecção por regra é
Policy pura, e `pricing_policy.evaluate()` já prova o molde. Rodar num Cloud Run Job (como o
`migrate`) mantém a detecção fora do request path e do grafo (ADR-019). O índice único parcial
`WHERE status='OPEN'` faz o banco impor idempotência do re-scan. Gerar `opportunity` e parar
(sem mensagem) respeita SPEC-019/022 e deixa o outreach para a fatia OUTBOUND com seu policy gate
(ADR-020).

## Consequências
- +1 tabela, +1 migration, +1 policy, +1 repositório, +1 serviço, +1 script, +1 recurso IaC (Job).
- +1 `SELECT` (candidatos) + N `INSERT ... ON CONFLICT` por execução; 0 chamadas LLM.
- `opportunity` OPEN pode ficar "stale" (sinal já resolvido) até a fatia de ciclo de vida.
- `probability` 0.35 / 0.45 são placeholders — calibrar quando houver dados.
- A query de candidatos de replenishment duplica o CTE de janela do `customer_360` — aceito
  (formatos de query distintos: 1 cliente vs. scan de todos).
- `QuoteStatus` não tem estado "recusado" — todo `quote SENT` sem order é candidato; se um
  `REJECTED`/`DECLINED` surgir, a query precisa excluí-lo.
- Sem Cloud Scheduler: o "automaticamente" do PRD-010 depende de alguém rodar o Job (ou do
  follow-up). Sem infra nova além do Job, sem secret novo. A `0007` roda pelo
  `revenueflow-api-migrate`.

## Regra de revisão
Mudanças nesta decisão — em especial pôr o LLM no caminho da detecção, mover a regra para dentro
do grafo, ou o Opportunity Engine passar a disparar contato ativo diretamente — exigem novo ADR
ou superseding ADR.
