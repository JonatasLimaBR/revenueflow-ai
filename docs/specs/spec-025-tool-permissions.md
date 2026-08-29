# SPEC-025 — Tool Permissions

## Objetivo
Aplicar least privilege.

## Contrato / Dados
agent_role -> allowed_tools

## Regra de implementação
Product Agent não cria pedido; Order Agent não altera preço.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
