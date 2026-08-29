# ADR-025 — Tools financeiras determinísticas

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Pricing, inventory, order e payment serão APIs determinísticas.

## Alternativas consideradas
Executar lógica dentro do agente.

## Motivo
Permite testes e controle.

## Consequências
Mais serviços/tool wrappers.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
