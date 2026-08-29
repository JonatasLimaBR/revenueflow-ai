# SPEC-028 — Audit Trail

## Objetivo
Registrar decisões e execução.

## Contrato / Dados
trace_id, conversation_id, agent, model, prompt_version, tool, action, result, latency, token_usage, cost, timestamp

## Regra de implementação
Obrigatório para ações comerciais.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
