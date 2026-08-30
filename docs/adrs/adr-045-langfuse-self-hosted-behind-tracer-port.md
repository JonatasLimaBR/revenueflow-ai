# ADR-045 — Langfuse self-hosted atrás de uma porta Tracer

## Status
Accepted

## Contexto
O ADR-040 exige tracing reconstruível desde a primeira fatia funcional: nó, tool, prompt, versão de prompt, tokens, custo, decisão de política e resultado final, com PII mascarada antes do sink. É preciso fixar a plataforma de tracing, o esquema do registro e os pontos de instrumentação sem acoplar o `domain` a bibliotecas de LLM.

## Decisão
Adotar **Langfuse self-hosted** como sink padrão, atrás de uma porta `Tracer` definida na camada de observabilidade. Implementações: `LangfuseTracer` (ambiente e desenvolvimento), `OTelTracer` (fallback compatível com OpenTelemetry) e `NoopTracer` (testes), selecionadas por `TRACER_SINK`. O Langfuse roda no `docker-compose` local. O esquema do trace é uma árvore `conversation → turn → {node, tool.<nome>, llm.<generation>}` com `mask()` aplicada a entradas, saídas e prompts na borda, e o custo derivado de `Usage` por uma tabela de preços de modelo.

## Alternativas consideradas
- Somente OpenTelemetry: não modela generation, versão de prompt e custo de forma nativa; exigiria reimplementar as convenções que o Langfuse já entrega.
- Langfuse SaaS: PII sai da fronteira, desenvolvimento offline quebra e contraria os controles de isolamento e retenção do skill `gcp-security`.
- Adiar observabilidade para depois do MVP: viola explicitamente o ADR-040.

## Motivo
O Langfuse dá as visões nativas de LLM (generation, prompt version, tokens, custo) que a lista de campos do ADR-040 pede. Self-hosted resolve residência de dados e permite desenvolvimento offline. A porta mantém o `domain` livre de dependência de LLM e permite trocar o sink sem tocar nos nós.

## Consequências
Mais dois contêineres no `docker-compose` (Langfuse e o seu PostgreSQL). Investimento antecipado em mascaramento de PII e numa tabela de preços de modelo (valores a confirmar via MCP `gcp-cli`). Em troca, qualquer mensagem processada é reconstruível desde o primeiro commit.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
