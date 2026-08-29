# ADR-027 — GCP como System of Record

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
PostgreSQL + BigQuery são fontes principais.

## Alternativas consideradas
Databricks como fonte principal.

## Motivo
Simplificar operação.

## Consequências
Portabilidade exige abstração.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
