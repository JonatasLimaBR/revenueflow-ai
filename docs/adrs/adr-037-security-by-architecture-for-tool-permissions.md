# ADR-037 — Security by Architecture for Tool Permissions

## Status
Accepted

## Contexto
Prompt instructions sozinhas não impedem um agente de usar uma ferramenta perigosa caso ela esteja registrada em seu contexto.

## Decisão
Permissões serão aplicadas estruturalmente: cada agente só recebe as tools necessárias à sua função.

## Alternativas consideradas
- Registrar todas as tools e instruir o agente a não usar algumas.
- Usar apenas system prompt para controle.

## Motivo
Ausência de capacidade é mais segura que proibição textual.

## Consequências
Será necessário manter manifests explícitos de tools por agente e testes de privilege escalation.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
