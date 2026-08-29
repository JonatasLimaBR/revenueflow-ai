# PRD-008 — Pedidos e Confirmação

## Objetivo
Criar pedido simulado somente após confirmação explícita do cliente e revalidação das condições.

## Escopo
- Confirmação explícita.
- Revalidação de estoque.
- Revalidação de preço quando necessário.
- Criação idempotente do pedido.
- Status operacional.

## Regra crítica
Nenhum pedido será criado a partir de intenção ambígua.

## Métricas
- Pedidos criados.
- Erros de pedido.
- Conversão proposta → pedido.
