# PRD-004 — Catálogo e Recomendação de Produtos

## Problema
O cliente descreve uma necessidade, mas nem sempre conhece SKU, categoria ou especificação.

## Objetivo
Permitir busca e recomendação baseada em linguagem natural sem permitir que o LLM invente produtos.

## Escopo
- Catálogo estruturado.
- Busca semântica.
- Filtros.
- Especificações técnicas.
- Compatibilidade.
- Evidência da recomendação.
- Confidence score.

## Regra crítica
Todo produto recomendado deve existir no catálogo autorizado.

## Métricas
- Product Recommendation Accuracy.
- Taxa de recomendações com evidência.
- Taxa de fallback para humano.
