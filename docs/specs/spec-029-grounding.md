# SPEC-029 — Grounding

## Objetivo
Impedir que LLM seja fonte de verdade para dados críticos.

## Contrato / Dados
price, inventory, order, payment, customer data

## Regra de implementação
Somente APIs/bancos/tools autorizadas.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
