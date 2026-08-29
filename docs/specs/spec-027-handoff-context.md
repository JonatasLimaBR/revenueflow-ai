# SPEC-027 — Handoff Context

## Objetivo
Entregar resumo estruturado ao humano.

## Contrato / Dados
conversation_summary, customer, intent, products, quote, objections, reason, next_best_action

## Regra de implementação
Evitar exigir leitura integral da conversa.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
