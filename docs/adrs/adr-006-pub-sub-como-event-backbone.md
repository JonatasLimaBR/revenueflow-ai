# ADR-006 — Pub/Sub como event backbone

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar Pub/Sub para eventos de domínio.

## Alternativas consideradas
Integrações totalmente síncronas.

## Motivo
Reduz acoplamento e melhora resiliência.

## Consequências
Exige idempotência.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
