# SPEC-014 — Confirmation

## Objetivo
Exigir confirmação explícita antes de criar pedido.

## Contrato / Dados
customer_message, intent_confirmation

## Regra de implementação
'Sim, pode fechar' é válido; linguagem ambígua não.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
