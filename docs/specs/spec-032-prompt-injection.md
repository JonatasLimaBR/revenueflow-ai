# SPEC-032 — Prompt Injection

## Objetivo
Bloquear tentativa de modificar regras internas.

## Contrato / Dados
user_input, system_rules, tool_permissions

## Regra de implementação
Mensagem do cliente não altera políticas ou alçadas.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
