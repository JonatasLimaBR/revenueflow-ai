# ADR-032 — PII minimization

## Status
Accepted

## Contexto
Esta decisão faz parte da arquitetura do RevenueFlow AI e deve permanecer explícita para evitar implementação por acaso ou por preferência implícita.

## Decisão
Enviar ao LLM apenas dados pessoais necessários.

## Alternativas consideradas
Enviar Customer 360 completo.

## Motivo
Reduz exposição e risco.

## Consequências
Exige context builders.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
