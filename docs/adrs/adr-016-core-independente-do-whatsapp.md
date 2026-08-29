# ADR-016 — Core independente do WhatsApp

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Separar adapter do canal do Sales Core.

## Alternativas consideradas
Lógica dentro do webhook.

## Motivo
Permite novos canais no futuro.

## Consequências
Mais abstrações iniciais.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
