# ADR-021 — Idempotência obrigatória

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar idempotency_key em operações críticas.

## Alternativas consideradas
Confiar em entrega única.

## Motivo
APIs externas podem duplicar eventos.

## Consequências
Necessidade de armazenamento de chaves.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
