# SPEC-036 — Testing

## Objetivo
Definir suíte mínima de testes.

## Contrato / Dados
unit, integration, AI eval, security tests

## Regra de implementação
Cobrir pricing, margin, tools, prompt injection, order.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
