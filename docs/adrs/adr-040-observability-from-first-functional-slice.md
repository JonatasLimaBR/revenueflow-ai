# ADR-040 — Observability From First Functional Slice

## Status
Accepted

## Contexto
Depurar comportamento agentic sem trace transforma falhas em adivinhação.

## Decisão
Tracing e correlação por sessão entram desde a primeira fatia funcional.

## Alternativas consideradas
- Adicionar observabilidade após o MVP.
- Usar somente logs de aplicação.

## Motivo
Ferramentas, decisões, prompts, custos e políticas precisam ser reconstruíveis desde o início.

## Consequências
A V1 terá investimento antecipado em tracing e sanitização de PII.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
