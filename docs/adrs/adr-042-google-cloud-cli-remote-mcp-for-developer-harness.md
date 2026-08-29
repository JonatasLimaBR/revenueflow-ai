# ADR-042 — Google Cloud CLI Remote MCP for Developer Harness

## Status
Accepted

## Contexto
Claude Code precisa inspecionar GCP com contexto autorizado sem criar wrappers ad hoc para cada operação.

## Decisão
Usar o Google Cloud CLI remote MCP como MCP GCP principal do harness de desenvolvimento.

## Alternativas consideradas
- wrappers locais para gcloud;
- GKE MCP como MCP principal;
- nenhuma integração MCP.

## Motivo
O Cloud CLI MCP fornece uma fronteira padrão e usa a identidade/IAM do Google Cloud.

## Consequências
O recurso é Preview/Pre-GA e não poderá ser dependência do runtime da aplicação. Mudanças destrutivas permanecem bloqueadas por hooks/IAM/revisão.

## Regra de revisão
Mudança desta decisão exige ADR superseding.
