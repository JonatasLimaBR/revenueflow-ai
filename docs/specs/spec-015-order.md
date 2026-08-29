# SPEC-015 — Order

## Objetivo
Criar pedido simulado de forma idempotente.

## Contrato / Dados
order_id, customer_id, quote_id, products, prices, quantity, total, status

## Regra de implementação
Revalidar estoque antes da criação.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
