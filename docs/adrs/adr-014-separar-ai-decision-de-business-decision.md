# ADR-014 — Separar AI Decision de Business Decision

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
LLM/ML recomenda; Policy Engine decide; API executa.

## Alternativas consideradas
LLM decide e executa.

## Motivo
Mantém decisões financeiras auditáveis.

## Consequências
Mais componentes.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
