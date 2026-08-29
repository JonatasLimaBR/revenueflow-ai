# SPEC-003 — Identificação do Cliente

## Objetivo
Identificar cliente pelo telefone; se não existir, criar lead provisório.

## Contrato / Dados
phone, customer_id, lead_id

## Regra de implementação
Nunca misturar contexto entre clientes.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
