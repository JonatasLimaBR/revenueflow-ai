# SPEC-009 — Pricing Service

## Objetivo
Consultar preço autorizado por cliente/produto/quantidade.

## Contrato / Dados
customer_id, product_id, quantity -> list_price, customer_price, maximum_discount, minimum_margin, valid_until

## Regra de implementação
LLM não calcula preço final sozinho.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
