# SPEC-010 — Pricing Guardrail

## Objetivo
Garantir margem mínima e limites de desconto.

## Contrato / Dados
revenue, cost, gross_profit, margin

## Regra de implementação
Margem abaixo do mínimo exige aprovação.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
