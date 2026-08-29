# ADR-004 — PostgreSQL como OLTP

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar Cloud SQL PostgreSQL como banco operacional.

## Alternativas consideradas
Firestore, BigQuery.

## Motivo
Transações e relacionamentos fortes favorecem SQL relacional.

## Consequências
Requer gestão de conexões e migrations.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
