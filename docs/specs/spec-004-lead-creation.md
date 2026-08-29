# SPEC-004 — Lead Creation

## Objetivo
Criar lead com dados progressivos coletados durante a conversa.

## Contrato / Dados
lead_id, phone, name, company, city, industry, need, urgency, estimated_value, score, status

## Regra de implementação
Status: NEW, QUALIFYING, QUALIFIED, PROPOSAL, WON, LOST.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
