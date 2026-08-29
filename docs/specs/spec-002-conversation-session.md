# SPEC-002 — Conversation Session

## Objetivo
Criar e manter sessão conversacional vinculada a customer_id ou lead_id.

## Contrato / Dados
conversation_id, phone, status, current_intent, current_agent, last_interaction

## Regra de implementação
Status: OPEN, WAITING_CUSTOMER, WAITING_APPROVAL, HUMAN_HANDOFF, CLOSED.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
