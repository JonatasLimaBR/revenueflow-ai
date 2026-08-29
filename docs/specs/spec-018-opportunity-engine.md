# SPEC-018 — Opportunity Engine

## Objetivo
Detectar oportunidades comerciais por regras e/ou modelos.

## Contrato / Dados
customer_id, opportunity_type, product, estimated_revenue, probability, reason, recommended_action

## Regra de implementação
Tipos controlados.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
