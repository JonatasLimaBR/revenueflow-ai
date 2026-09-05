# ADR-063 — ANALYTICS_360: os 4 domínios restantes do PRD-015 (Customer/Lead/Opportunity 360 + Conversation Analytics)

## Status
Accepted

## Contexto
ADR-061 fechou só Revenue + Custo de IA do PRD-015, explicitamente deixando os outros 4 domínios
(Customer 360, Lead 360, Opportunity 360, Conversation Analytics) para uma fatia futura. O usuário
pediu essa fatia. LEAD_LIFECYCLE (ADR-062, fatia anterior) deu dado real ao funil de lead — antes,
`LeadStatus` nunca avançava de `NEW`, o que teria tornado Lead 360 um relatório de dado vazio.

## Decisão

- **4 views novas no Postgres (`migrations/0014`), mesmo padrão do ADR-061 — nenhuma toca as 4
  views existentes.** `v_customer_360_all` (1 linha por cliente, incl. sem pedido — `orders_12m=0`
  via `LEFT JOIN`/`coalesce`, não ausente); `v_lead_funnel` (`lead_id`/`status`/`created_at`, sem
  telefone); `v_opportunity_summary` (campos numéricos/categóricos, sem `reason`/`evidence`);
  `v_handoff_rate` (contagem de turnos com `handoff=true` sobre o total, de `audit_event`).
- **`v_customer_360_all` via `agg`/`preferred_agg`+`preferred` split, não janela direta sobre
  `sum()`.** `preferred_agg` agrega `sum(last_qty)` por `(customer_id, product_id)` primeiro;
  `preferred` roda `row_number() OVER (... ORDER BY qty DESC)` sobre esse resultado já agregado —
  agregação direta dentro do `OVER` é inválida em SQL.
- **`services.analytics_sync.run()` generalizado para uma lista `_SOURCES` de 6 entradas**, em vez
  de 6 blocos `if _load(...): ... else: errors += 1` repetidos. Cada entrada é
  `(nome_tabela_bigquery, nome_função_em_analytics_repo, schema)` — a função é resolvida via
  `getattr(analytics_repo, fn_name)` **a cada chamada**, não vinculada como referência direta no
  momento de import do módulo. Isso é deliberado: a suíte de testes já usa
  `monkeypatch.setattr(analytics_repo, "conversation_revenue", ...)`, e uma referência de função
  capturada antes do monkeypatch nunca veria o patch.
- **`SyncResult` muda de campos fixos (`conversation_rows`/`outcome_rows`) para `rows_loaded:
  dict[str, int]`.** Mudança de contrato pequena — só `scripts/sync_analytics.py` consome o shape
  antigo — aceitável para generalizar de 2 para 6 cargas sem um campo por tabela.
- **`infra/terraform/analytics.tf` += 4 tabelas de fato + 3 views**, mesmo dataset
  `revenueflow_analytics`, mesmo IAM já escopado (ADR-008) — nenhum binding novo. Views:
  `v_lead_conversion` (`GROUP BY status`, contagem — taxa de conversão fica pro consumidor,
  `WON / SUM(leads)` é mais simples que embutir no SQL); `v_opportunity_pipeline` (soma de
  `estimated_revenue` só `status='OPEN'`, por tipo); `v_opportunity_conversion`
  (`SAFE_DIVIDE(COUNTIF(status='CONVERTED'), COUNT(*))` por tipo).

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Dashboard/Looker Studio — as tabelas ficam prontas para qualquer consumidor, nenhuma ferramenta
  de BI é conectada.
- Histórico de tendência — cada sync sobrescreve o snapshot atual (`WRITE_TRUNCATE`), mesma decisão
  do ADR-061.
- Exportar `reason`/`evidence` (texto livre) de `opportunity`, ou telefone/nome — minimização de
  PII (ADR-032), mesmo padrão do ADR-061.
- Cloud Scheduler para o sync — mesma decisão adiada, 3ª vez consecutiva.

## Alternativas consideradas

- **Vincular `analytics_repo.<fn>` diretamente na lista `_SOURCES`** (referência de função, não
  nome) — mais direto de ler, mas quebra silenciosamente o `monkeypatch.setattr` da suíte de testes
  existente, porque a referência já estaria capturada antes do patch. Rejeitado.
- **Um campo fixo por tabela em `SyncResult`** (`customer_360_rows`, `lead_funnel_rows`, ...) —
  mantém o shape anterior, mas duplica a lista `_SOURCES` numa segunda estrutura paralela sem
  necessidade; `dict[str, int]` é suficiente para o único consumidor (`scripts/sync_analytics.py`).
- **Calcular a taxa de conversão de lead dentro da view `v_lead_conversion`** — exigiria conhecer
  todos os status possíveis dentro do SQL; `GROUP BY status` bruto é mais simples e o cálculo final
  (`WON / SUM(leads)`) é trivial no consumidor.

## Motivo
O usuário pediu explicitamente os 4 domínios restantes do PRD-015 como fatia nova, e LEAD_LIFECYCLE
já removeu o motivo real para adiar Lead 360 (funil vazio). O corte replica exatamente o mecanismo
já validado em ANALYTICS/ADR-061 (view Postgres → repositório → sync batch → tabela BigQuery),
generalizado de 2 para 6 cargas — nenhum padrão novo, só extensão do existente.

## Consequências
- +4 views no Postgres (`0014`, ao lado das existentes); +4 tabelas + 3 views no BigQuery (mesmo
  dataset, sem IAM novo); `services.analytics_sync.run()` passa a resolver a função de fetch por
  nome a cada chamada, um nível de indireção a mais do que uma lista de referências diretas, mas
  necessário para o monkeypatch dos testes continuar funcionando; +ADR-063.
- Sem dependência nova, sem migração de IAM, sem infraestrutura fora do dataset já existente.
- Uma regressão que reintroduza uma referência de função direta em `_SOURCES` (em vez de
  `getattr` por nome) quebraria silenciosamente o monkeypatch dos testes existentes — pegar isso
  em revisão de código, já que o teste em si passaria mesmo com o bug (chamaria a função real, não
  o mock, mas sem erro se um Postgres real estiver acessível).

## Regra de revisão
Mudanças nesta decisão — em especial voltar a vincular funções diretamente em `_SOURCES`, exportar
`reason`/`evidence`/telefone para o BigQuery, ou introduzir Cloud Scheduler — exigem novo ADR ou
superseding ADR.
