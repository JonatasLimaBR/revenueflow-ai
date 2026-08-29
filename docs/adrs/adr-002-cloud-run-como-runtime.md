# ADR-002 — Cloud Run como runtime

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Executar backend FastAPI em Cloud Run.

## Alternativas consideradas
GKE, Compute Engine, Cloud Functions.

## Motivo
Menor complexidade operacional para V1.

## Consequências
Cold starts e conexão com banco devem ser monitorados.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
