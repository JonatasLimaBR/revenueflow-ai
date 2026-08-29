# SPEC-008 — Inventory Service

## Objetivo
Consultar disponibilidade e prazo.

## Contrato / Dados
product_id, quantity -> available, available_quantity, warehouse, expected_delivery, timestamp

## Regra de implementação
Nunca declarar estoque sem resposta válida.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
