# ADR-039 — Persistent Interrupt Before Irreversible Actions

## Status
Accepted

## Contexto
Ações como desconto excepcional, pedido de alto valor e condições especiais não devem depender apenas de uma instrução textual.

## Decisão
O workflow deverá executar `interrupt` antes da ação crítica, persistir checkpoint e exigir aprovação válida para continuar.

## Alternativas consideradas
- Confirmar somente via prompt.
- Criar a ação e reverter depois.

## Motivo
A pausa deve ser um primitivo do workflow, não apenas uma etapa visual.

## Consequências
Aprovação passa a ser parte do estado do domínio e deve possuir testes de transição.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
