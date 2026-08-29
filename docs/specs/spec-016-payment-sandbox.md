# SPEC-016 — Payment Sandbox

## Objetivo
Executar pagamento somente em ambiente de teste.

## Contrato / Dados
payment_id, order_id, amount, status

## Regra de implementação
Nunca armazenar dados sensíveis de cartão.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
