# ADR-043 — Claude Code Hooks Block Destructive GCP Actions

## Status
Accepted

## Contexto
Um agente de código com shell pode executar comandos destrutivos por engano.

## Decisão
Adicionar PreToolUse hook para bloquear padrões destrutivos e ações Terraform apply/destroy.

## Alternativas consideradas
- confiar apenas no prompt;
- permitir tudo e depender de revisão posterior.

## Motivo
Bloqueio pré-execução reduz risco e torna a regra executável.

## Consequências
Algumas operações legítimas exigirão execução humana explícita.

## Regra de revisão
Mudança desta decisão exige ADR superseding.
