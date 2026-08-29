# SPEC-022 — Outbound Contact

## Objetivo
Controlar contato ativo.

## Contrato / Dados
Opportunity -> Contact Policy -> Consent Check -> Campaign Candidate -> Message

## Regra de implementação
Opportunity Engine não dispara WhatsApp diretamente.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
