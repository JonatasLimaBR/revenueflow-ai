# SPEC-019 — Replenishment Rule

## Objetivo
Detectar recompra atrasada.

## Contrato / Dados
days_since_last_purchase > average_purchase_interval * threshold

## Regra de implementação
Gerar opportunity, não mensagem.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
