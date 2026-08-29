# ADR-033 — Customer 360 não vai inteiro ao LLM

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar tool específica para contexto comercial mínimo.

## Alternativas consideradas
SELECT * e prompt completo.

## Motivo
Least privilege também vale para contexto.

## Consequências
Mais APIs de contexto.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
