# SPEC-034 — Observability

## Objetivo
Coletar métricas técnicas e de IA.

## Contrato / Dados
request_count, response_time, error_rate, tool_failures, token_usage, cost, handoffs

## Regra de implementação
Dashboards e alertas básicos.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
