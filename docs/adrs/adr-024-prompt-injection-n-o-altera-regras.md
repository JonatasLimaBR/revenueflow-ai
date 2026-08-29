# ADR-024 — Prompt injection não altera regras

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usuário não modifica system rules, tool permissions ou pricing policies.

## Alternativas consideradas
Confiar somente em prompt.

## Motivo
Segurança não pode depender do comportamento do modelo.

## Consequências
Necessidade de policy enforcement fora do LLM.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
