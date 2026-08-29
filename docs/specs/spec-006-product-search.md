# SPEC-006 — Product Search

## Objetivo
Buscar produtos apenas por ferramenta autorizada.

## Contrato / Dados
query, filters, customer_context -> product_id, sku, name, attributes, compatibility

## Regra de implementação
LLM não inventa SKU.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
