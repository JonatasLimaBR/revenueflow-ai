# SPEC-035 — Performance

## Objetivo
Definir meta de latência.

## Contrato / Dados
P95

## Regra de implementação
Objetivo inicial: P95 < 5s para fluxos simples.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
