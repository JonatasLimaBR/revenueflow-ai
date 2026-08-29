# SPEC-023 — Agent Supervisor

## Objetivo
Orquestrar workflow e selecionar agentes.

## Contrato / Dados
conversation_context, intent, policies, tools

## Regra de implementação
Responsável por fallback e handoff.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
