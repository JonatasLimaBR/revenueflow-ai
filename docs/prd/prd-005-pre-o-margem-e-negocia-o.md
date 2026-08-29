# PRD-005 — Preço, Margem e Negociação

## Problema
Um agente generativo não pode possuir liberdade para inventar preço ou conceder descontos que destruam margem.

## Objetivo
Permitir negociação natural com limites financeiros determinísticos.

## Escopo
- Preço de tabela.
- Preço por cliente.
- Desconto máximo.
- Margem mínima.
- Alçadas.
- Simulação de alternativas.
- Aprovação humana.

## Regra crítica
O LLM interpreta a negociação; o Pricing Engine calcula e valida.

## Métricas
- Margem preservada.
- Desconto médio.
- Aprovações solicitadas.
- Conversão após negociação.
