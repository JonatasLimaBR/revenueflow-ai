# SPEC-001 — WhatsApp Webhook

## Objetivo
Receber eventos do WhatsApp Business Platform com validação, persistência e idempotência.

## Contrato / Dados
event_id, timestamp, phone, message_id, message_type, message_text

## Regra de implementação
Eventos duplicados não podem ser reprocessados.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
