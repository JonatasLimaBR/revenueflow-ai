# SPEC-011 — Negotiation Agent

## Objetivo
Interpretar objeções e negociar apenas dentro da política.

## Contrato / Dados
requested_discount, quantity, alternatives

## Regra de implementação
Não altera custo, margem mínima ou limite.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
