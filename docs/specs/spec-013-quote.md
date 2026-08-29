# SPEC-013 — Quote

## Objetivo
Gerar proposta rastreável e versionada.

## Contrato / Dados
quote_id, customer_id, items, quantity, unit_price, discount, freight, total, expiration, status

## Regra de implementação
Somente preços autorizados.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
