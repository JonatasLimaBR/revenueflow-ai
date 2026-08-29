# SPEC-024 — Allowed Agents

## Objetivo
Definir conjunto de agentes da V1.

## Contrato / Dados
Customer, Lead, Product, Inventory, Pricing, Negotiation, Opportunity, Order

## Regra de implementação
Nenhum agente possui todas as tools.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
