# MCP — RevenueFlow AI

## MCP principal

O arquivo `.mcp.json` registra o Google Cloud CLI remote MCP:

```text
https://cloudcli.googleapis.com/mcp
```

Use este MCP para inspeção e operações autorizadas do Google Cloud.

## Princípio de segurança

MCP não substitui IAM.

Claude deve possuir somente as permissões que a identidade Google autenticada possui.

## GKE MCP opcional

O RevenueFlow AI usa Cloud Run na V1, portanto GKE MCP não é dependência.

Se uma futura ADR migrar workloads para GKE, consulte `mcp/gke-mcp.example.json`.

## Regra

Não adicionar um MCP com poder de escrita sem:
1. ADR;
2. threat model;
3. tool permission matrix;
4. testes de segurança;
5. aprovação humana.
