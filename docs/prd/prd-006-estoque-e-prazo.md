# PRD-006 — Estoque e Prazo

## Objetivo
Garantir que disponibilidade, quantidade e prazo informados ao cliente venham de fonte transacional autorizada.

## Escopo
- Consulta de estoque.
- Quantidade disponível.
- Warehouse.
- Prazo estimado.
- Revalidação antes do pedido.

## Regra crítica
O agente nunca poderá responder disponibilidade sem chamada válida ao Inventory Service.

## Métricas
- Inventory Tool Success Rate.
- Erros de disponibilidade.
- Divergência entre promessa e estoque.
