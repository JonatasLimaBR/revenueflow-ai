# ADR-010 — RAG apenas para conteúdo não estruturado

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Usar RAG para manuais, FAQ, políticas e catálogo textual.

## Alternativas consideradas
Indexar também dados transacionais.

## Motivo
Busca vetorial não garante estado atual.

## Consequências
Duas estratégias de acesso a dados.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
