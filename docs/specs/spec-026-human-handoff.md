# SPEC-026 — Human Handoff

## Objetivo
Transferir conversa em condições de risco ou pedido explícito.

## Contrato / Dados
low_confidence, repeated_errors, critical_complaint, out_of_policy, high_value_order

## Regra de implementação
Registrar motivo do handoff.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
