# SPEC-021 — Opportunity Entity

## Objetivo
Persistir oportunidade com explicabilidade.

## Contrato / Dados
opportunity_id, customer_id, type, product, estimated_revenue, probability, reason, recommended_action, status

## Regra de implementação
Obrigatório reason + evidence.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
