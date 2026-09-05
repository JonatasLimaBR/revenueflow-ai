# ADR-072 — Correção do ADR-071: `value_extractor` só existe pra métrica DISTRIBUTION

## Status
Accepted (supersede parcial do ADR-071)

## Contexto
ADR-071 tentou resolver "`ALIGN_SUM` não escalariza `DISTRIBUTION`" criando 2 métricas gêmeas sem
`bucket_options` (`value_type = "DOUBLE"`/`"INT64"`), reusando o mesmo `value_extractor`. Um
`apply` real contra produção (depois do bootstrap corrigido, ADR-069/070) rejeitou as duas:

```
Error: Error creating Metric: googleapi: Error 400: A value extractor can only be
specified for a DISTRIBUTION value type.
```

`value_extractor` — o campo que lê `jsonPayload.cost_usd`/`jsonPayload.tool_failures` de cada
linha de log e vira o valor do ponto de métrica — só é uma opção legal quando
`metric_descriptor.value_type = "DISTRIBUTION"`. Não existe, na API de log-based metrics do Cloud
Logging, uma forma de extrair um valor numérico arbitrário do payload e virar métrica plana
(DOUBLE/INT64) sem bucket — só contagem de linhas de log (com `label_extractors`) ou distribution.
Isso invalida o design do ADR-071 por completo, não só o aligner.

## Decisão

- **Reverter as 2 métricas gêmeas** (`turn_cost_usd_total`/`tool_failures_total`) — remover os
  recursos, voltar os 2 alertas a filtrar pelas métricas `DISTRIBUTION` originais.
- **Trocar `ALIGN_SUM` por `ALIGN_PERCENTILE_99`** nos 2 alertas (`tool_failures`,
  `ai_cost_per_hour`) — confirmado no ADR-071 que percentil é o único aligner que produz um
  escalar `DOUBLE` a partir de uma métrica DISTRIBUTION.
- **Documentar honestamente a mudança de semântica** — `display_name`/`documentation` de cada
  alerta atualizados pra dizer "p99 por turno", não mais "total na hora". O alerta agora detecta
  "o turno mais caro/com mais falhas da hora passou de X", não "a soma da hora passou de X" — uma
  proxy real e construível, não o KPI exato original do ADR-023/056, mas o mais próximo que a API
  permite sem uma alerta MQL (fora de escopo, ver abaixo).

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- **`condition_monitoring_query_language`** (MQL) em vez de `condition_threshold` — permitiria uma
  alerta de soma real via `sum_over_time`/`align_delta`, mas exigiria escrever e validar sintaxe
  MQL sem conseguir testar contra a API localmente antes do deploy — mesmo risco que já se
  materializou duas vezes nesta sessão (API do `mcp`, agora `value_extractor`). Fica como
  follow-up explícito quando puder ser validado com mais cautela.
- Mudar as métricas DISTRIBUTION pra outro tipo — o dashboard depende do histograma completo.

## Alternativas consideradas

- **Manter as métricas gêmeas, mas sem `value_extractor`** — sem `value_extractor`, uma métrica de
  log só conta ocorrências de linha de log (sempre 1 por entrada), não consegue carregar o valor
  numérico real de custo/falhas — inútil pro propósito do alerta.
- **MQL agora mesmo** — rejeitada por risco (ver "fora de escopo"); prefere-se uma correção
  simples e verificável (percentil) a uma reescrita mais poderosa mas não testável neste momento.

## Motivo
A segunda tentativa de `apply` real provou que o design do ADR-071 não era construível — não um
detalhe de sintaxe, mas uma regra da própria API do Cloud Logging. A correção mínima e
imediatamente verificável é reverter pro aligner que a documentação oficial já confirmou como
válido (percentil), aceitando a mudança de semântica e documentando-a com honestidade em vez de
inventar uma segunda tentativa de contornar a mesma regra.

## Consequências
- `infra/terraform/monitoring.tf`: -2 recursos (`turn_cost_usd_total`/`tool_failures_total`), 2
  alert policies revertidos pro filtro original + `ALIGN_PERCENTILE_99`; `depends_on` volta a só
  `google_project_service.this` (sem referência às métricas removidas).
- Os 2 alertas de custo/falha de ferramenta agora detectam picos por turno (p99), não gasto/falhas
  totais acumulados na janela — uma diferença real de comportamento que qualquer pessoa lendo os
  alertas no Cloud Monitoring precisa saber (documentado no `display_name`/`documentation` de cada
  um).
- ADR-071 permanece no histórico como registro do que foi tentado e por que não funcionou —
  não removido, só superado por este ADR-072 na parte específica da implementação (a causa raiz
  diagnosticada em ADR-071 — ALIGN_SUM não escalariza distribution — continua correta).

## Regra de revisão
Mudanças nesta decisão — em especial reintroduzir uma métrica gêmea com `value_extractor` fora de
uma DISTRIBUTION, ou migrar pra MQL sem validar a sintaxe contra a API antes do deploy — exigem
novo ADR ou superseding ADR.
