# SPEC-012 — Human Approval

## Objetivo
Criar solicitação de aprovação com contexto comercial completo.

## Contrato / Dados
approval_id, reason, customer, quote, requested_discount, current_margin, resulting_margin, amount

## Regra de implementação
Status: PENDING, APPROVED, REJECTED, EXPIRED.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
