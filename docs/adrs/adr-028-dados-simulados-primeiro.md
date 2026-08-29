# ADR-028 — Dados simulados primeiro

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Simular ERP, estoque, pricing e pedidos na V1.

## Alternativas consideradas
Integrações reais desde início.

## Motivo
Permite testar ponta a ponta sem dependências externas.

## Consequências
Mocks precisam refletir regras realistas.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
