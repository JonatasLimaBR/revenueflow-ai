# SPEC-020 — Quote Recovery

## Objetivo
Detectar proposta enviada sem conversão.

## Contrato / Dados
quote.status=SENT, elapsed_time>limit, order_not_created

## Regra de implementação
Gerar opportunity.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
