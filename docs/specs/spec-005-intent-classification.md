# SPEC-005 — Intent Classification

## Objetivo
Classificar intenção da mensagem em enum controlado.

## Contrato / Dados
greeting, product_search, recommendation, stock_request, price_request, quote_request, negotiation, order_request, order_status, cancellation, human_support, unknown

## Regra de implementação
Registrar intenção e confidence.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
