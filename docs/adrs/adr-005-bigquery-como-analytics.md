# ADR-005 — BigQuery como analytics

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar BigQuery para Customer 360 e Revenue Intelligence.

## Alternativas consideradas
PostgreSQL.

## Motivo
Separar OLTP de analytics.

## Consequências
Necessidade de sincronização de dados.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
