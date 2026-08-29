# SPEC-017 — Customer 360

## Objetivo
Construir visão analítica consolidada do cliente.

## Contrato / Dados
revenue_12m, orders_12m, average_ticket, last_purchase, purchase_interval, preferred_products, open_quotes, estimated_ltv, churn_score, next_best_action

## Regra de implementação
Expor ao LLM apenas o mínimo necessário.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
