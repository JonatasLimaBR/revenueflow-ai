# SPEC-033 — Idempotency

## Objetivo
Garantir execução única de operações críticas.

## Contrato / Dados
idempotency_key

## Regra de implementação
Aplicar em webhook, quote, order, payment.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
