# ADR-061 — ANALYTICS: sync batch Postgres → BigQuery, domínio Revenue + Custo de IA

## Status
Accepted

## Contexto
PRD-015 pede medir o impacto comercial do RevenueFlow AI em 5 domínios (Customer 360, Lead 360,
Revenue 360, Opportunity 360, Conversation Analytics) e 7 KPIs. ADR-005 já decidiu BigQuery para
isso; ADR-056 já previu esta fatia explicitamente como pós-V1 ("traria BigQuery e custo recorrente
para a V1"). O OLTP já calcula boa parte do custo/receita por conversa (`v_ai_cost_per_conversation`,
`v_ai_cost_per_outcome`, `v_ai_cost_per_revenue`), mas isso vive só no Postgres transacional, sem
separação de carga analítica (o motivo original do ADR-005), sem margem e sem receita recuperada
calculadas em lugar nenhum.

O usuário confirmou, via discovery, seguir com BigQuery (aceitando o custo recorrente novo) e
escolheu o domínio **Revenue + Custo de IA** como corte do MVP entre os 5 do PRD-015.

## Decisão

- **Sync batch `WRITE_TRUNCATE`, não streaming/CDC.** Um Cloud Run Job
  (`revenueflow-analytics-sync`, mesmo padrão de `opportunity-scan`/`campaign-run`) lê 2 views do
  Postgres e recarrega 2 tabelas do BigQuery **inteiras** a cada execução — snapshot atual, não
  log de eventos. Idempotente por construção (sem duplicata possível). On-demand nesta V1; Cloud
  Scheduler é follow-up.
- **Lógica de negócio só no Postgres (ADR-004).** `v_conversation_revenue` (view nova,
  `migrations/0013`) calcula margem (receita menos custo dos itens, via
  `jsonb_array_elements` + `sim_product.unit_cost`) e receita recuperada (pedidos cujo `quote_id`
  aparece numa `opportunity(QUOTE_RECOVERY)`) — uma vez só, em SQL do Postgres. O BigQuery recebe
  o resultado já calculado; nenhuma lógica de negócio é reimplementada em SQL de outro dialeto.
- **View nova, independente — `v_ai_cost_per_revenue` não é tocada.** `v_conversation_revenue` é
  criada **ao lado** das 3 views existentes (`v_ai_cost_per_conversation`, `v_ai_cost_per_outcome`,
  `v_ai_cost_per_revenue`), sem `DROP`/`ALTER`. `tests/integration/test_ai_cost_revenue_view.py`
  consulta `v_ai_cost_per_revenue` diretamente — removê-la quebraria esse teste.
- **`FLOAT64` no BigQuery, não `NUMERIC`.** Métricas agregadas de dashboard não exigem a precisão
  exata de `NUMERIC`/`BIGNUMERIC`; `FLOAT64` serializa direto de `dict` JSON sem conversão
  especial de `Decimal`.
- **IAM escopado ao dataset (ADR-008).** `google_bigquery_dataset_iam_member` (`roles/bigquery.dataEditor`)
  no dataset `revenueflow_analytics`, não `google_project_iam_member` a nível de projeto;
  `roles/bigquery.jobUser` é a única permissão de projeto (necessária para submeter o load job).
- **`v_revenue_summary`** (view BigQuery, 1 linha) cobre as 5 KPIs do MVP num único SELECT:
  `total_revenue`, `total_recovered_revenue`, `total_margin`, `average_ticket`
  (`SAFE_DIVIDE(SUM(revenue), SUM(orders))`), `revenue_per_ai_cost_usd`
  (`SAFE_DIVIDE(SUM(revenue), SUM(ai_cost_usd))`).

## Fora de escopo (decisões explícitas de **não** fazer na V1)

- **Os outros 4 domínios do PRD-015** (Customer 360, Lead 360, Opportunity 360, Conversation
  Analytics) — o usuário escolheu Revenue + Custo de IA como MVP; ficam para fatias futuras.
- **KPIs "Conversão" e "Pipeline"** — pertencem a Opportunity 360/Conversation Analytics.
- **Sync incremental / CDC / Datastream** — volume simulado da V1 não justifica; `WRITE_TRUNCATE`
  batch é suficiente e muito mais barato.
- **Histórico de tendência** (1 linha por dia/partição) — cada sync sobrescreve o snapshot atual;
  um histórico real exigiria uma tabela append-only separada.
- **Dashboard / Looker Studio / visualização** — as tabelas ficam prontas para qualquer
  consumidor; nenhuma ferramenta de BI é conectada nesta fatia.
- **Alertas de negócio sobre os KPIs** — observabilidade de negócio, não engenharia de dados.
- **Metodologia de "receita incremental" vs. baseline** (ADR-035) — decisão de negócio, não de
  engenharia; a view expõe o dado bruto que esse cálculo vai precisar.
- **Cloud Scheduler para o sync** — mesma decisão adiada das 2 fatias batch anteriores.
- **Lógica de negócio duplicada em SQL do BigQuery** — margem/receita recuperada continuam
  calculadas uma vez só, no Postgres.

## Alternativas consideradas

- **Streaming via Datastream/CDC do Postgres pro BigQuery** — infraestrutura significativamente
  mais cara e complexa para um volume simulado pequeno; contradiz a sensibilidade a custo
  confirmada na discovery.
- **Recalcular margem/receita recuperada em SQL do BigQuery** (exportar tabelas cruas) — duplicaria
  a lógica de negócio em dois dialetos SQL (Postgres `jsonb_array_elements` vs. BigQuery
  `JSON_VALUE`), maior superfície de bug por divergência silenciosa.
- **`DROP`/renomear `v_ai_cost_per_revenue`** — quebraria `test_ai_cost_revenue_view.py`.
- **`NUMERIC`/`BIGNUMERIC` no BigQuery** — precisão desnecessária para KPI de dashboard; mais
  fricção de serialização sem ganho real.
- **IAM de projeto (`roles/bigquery.dataEditor` global)** — violaria ADR-008 (least privilege);
  o dataset é o escopo correto.

## Motivo
ADR-005 pede BigQuery para Revenue Intelligence — esta fatia é a primeira a cumprir isso de fato,
mesmo que só para o domínio Revenue. O corte (2 tabelas + 1 view, sync batch simples) é o menor
que entrega valor real (dado migra pra BigQuery, separado da carga OLTP) sem inventar uma pipeline
de streaming que a V1 não precisa, e sem duplicar regra de negócio em dois lugares.

## Consequências
- +1 view no Postgres (`0013`, ao lado das existentes); +1 dataset BigQuery com 2 tabelas + 1
  view; +1 repositório + 1 serviço + 1 script; +1 Cloud Run Job; +1 extra opcional
  (`google-cloud-bigquery`, lazy); +ADR-061.
- Custo recorrente novo no GCP (dataset + load jobs) — confirmado explicitamente pelo usuário
  antes do build.
- 2 views com propósito sobreposto no Postgres (`v_ai_cost_per_revenue` e
  `v_conversation_revenue`) — aceito para não quebrar o teste existente; consolidar é um
  follow-up se a view antiga for depreciada.
- `WRITE_TRUNCATE` sem lock entre execuções concorrentes do Job pode produzir um estado
  momentaneamente inconsistente — aceitável para consumo humano/dashboard nesta V1.
- Uma regressão que remova o `WRITE_TRUNCATE`, mova IAM para nível de projeto, ou vaze PII
  (telefone/nome) para as tabelas BigQuery deveria ser pega em revisão manual (sem teste de
  BigQuery real no CI).

## Regra de revisão
Mudanças nesta decisão — em especial trocar `WRITE_TRUNCATE` por incremental/CDC, mover a lógica
de negócio para SQL do BigQuery, ou ampliar o escopo para os outros 4 domínios do PRD-015 sem um
novo ADR — exigem novo ADR ou superseding ADR.
