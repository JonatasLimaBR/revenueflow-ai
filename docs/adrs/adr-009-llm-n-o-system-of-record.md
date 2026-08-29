# ADR-009 — LLM não é System of Record

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
LLM não é fonte de verdade para preço, estoque, cliente, pedido ou pagamento.

## Alternativas consideradas
Responder por memória/RAG.

## Motivo
Evitar hallucination em dados críticos.

## Consequências
Mais tool calls e latência.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
