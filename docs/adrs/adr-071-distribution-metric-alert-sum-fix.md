# ADR-071 — `ALIGN_SUM` não escalariza métrica DISTRIBUTION: métricas gêmeas pra alerta

## Status
Accepted

## Contexto
Depois do bootstrap corrigido (ADR-069/070) e um `apply` real conseguindo criar quase tudo
(dashboard, Load Balancer, BigQuery, Cloud Run), sobraram 2 erros:

1. `google_monitoring_alert_policy.tool_failures` — `404: Cannot find metric(s)... could take up
   to 10 minutes to become available` (atraso de propagação, não é bug).
2. `google_monitoring_alert_policy.ai_cost_per_hour` — `400: a time series of type DISTRIBUTION
   cannot be compared directly to a literal numeric threshold without first converting to a scalar
   via an explicit aligner such as ALIGN_PERCENTILE_50/95/99`.

Confirmado contra a documentação oficial do Cloud Monitoring: `ALIGN_SUM` sobre uma métrica
`DISTRIBUTION` **não** reduz a um escalar (preserva o tipo distribution) — só os aligners de
percentil produzem um valor `DOUBLE`. `revenueflow_turn_cost_usd` e `revenueflow_tool_failures`
são `DISTRIBUTION` de propósito (o dashboard usa o histograma completo, ADR-056), mas os 2 alertas
querem "soma total na janela", não um percentil — trocar o aligner pra percentil mudaria o
significado do alerta (de "gasto total > $X/hora" pra "o turno mais caro > $X").

## Decisão

- **2 métricas novas, gêmeas, sem `bucket_options`** — `revenueflow_turn_cost_usd_total` (DOUBLE) e
  `revenueflow_tool_failures_total` (INT64) — mesmo `filter`/`value_extractor` das originais, só
  sem tipo distribution. `ALIGN_SUM` funciona corretamente sobre elas.
- **As métricas DISTRIBUTION originais continuam existindo, inalteradas** — o dashboard
  (`dashboards/revenueflow_ops.json`) continua apontando pra elas; só os 2 `filter` dos alert
  policies passam a apontar pras métricas `_total`.
- **`depends_on` explícito** nos 2 `google_monitoring_alert_policy` afetados, referenciando a
  métrica `_total` correspondente — o `filter` é uma string com o nome da métrica, não uma
  referência de atributo Terraform, então não havia aresta de dependência implícita; sem isso,
  Terraform podia tentar criar o alert policy antes (ou em paralelo com) a métrica.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Trocar as métricas DISTRIBUTION originais por escalares — o dashboard depende do histograma
  completo; substituir perderia informação (percentis, distribuição de custo por turno).
- Adicionar um `time_sleep` (provider `hashicorp/time`) pra absorver o atraso de propagação do
  `404` — o erro é auto-resolúvel numa nova tentativa de `apply` em poucos minutos; não vale a
  complexidade de um provider novo só pra isso na V1.

## Alternativas consideradas

- **`ALIGN_PERCENTILE_99` no lugar de `ALIGN_SUM`** — tecnicamente resolveria o erro, mas mudaria
  silenciosamente o que o alerta detecta (de gasto total acumulado pra um valor de percentil);
  rejeitado por misrepresentar a intenção original do ADR-056/023 (custo de IA como KPI de
  negócio — "quanto gastei", não "qual foi o turno mais caro").
- **Um `cross_series_reducer` em vez de métrica gêmea** — reduz entre séries (várias revisões do
  Cloud Run), não resolve o problema de reduzir uma distribution pra escalar dentro de uma série.

## Motivo
A causa raiz é uma regra real da API do Cloud Monitoring (confirmada na documentação oficial), não
um erro de configuração superficial. Duas métricas com o mesmo `value_extractor` — uma pro
histograma do dashboard, outra escalar pro alerta — é a correção mínima que preserva os dois usos
sem misrepresentar o significado de nenhum dos dois.

## Consequências
- +2 `google_logging_metric` em `monitoring.tf`; 2 `filter` de alert policy repontados; +2
  `depends_on` explícitos; +2 entradas em `_LOG_METRICS` (teste); +ADR-071.
- Mais um log-based metric por turno auditado (custo em dobro: uma entrada DISTRIBUTION, uma
  DOUBLE) — Cloud Logging cobra por volume de métrica escrita; efeito no custo é desprezível pro
  volume simulado da V1.
- O erro `404` do `tool_failures` original (propagação) deve resolver sozinho numa nova tentativa
  de `apply`, sem exigir mudança de código — só tempo.

## Regra de revisão
Mudanças nesta decisão — em especial remover uma das métricas gêmeas, ou trocar `ALIGN_SUM` por um
aligner de percentil sem atualizar a documentação do alerta pra refletir a mudança de semântica —
exigem novo ADR ou superseding ADR.
