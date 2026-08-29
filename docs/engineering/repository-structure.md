# Estrutura do Repositório

```text
revenueflow-ai/
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── prd/
│   ├── specs/
│   ├── adrs/
│   └── engineering/
├── src/revenueflow/
│   ├── api/
│   ├── agents/
│   ├── domain/
│   ├── services/
│   ├── tools/
│   ├── policies/
│   ├── repositories/
│   ├── events/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── ai_eval/
│   └── security/
├── scripts/
├── infra/terraform/
└── .github/workflows/
```

## Dependências permitidas
```text
api / agents
      ↓
services
      ↓
domain + policies
      ↓
repositories / adapters
```

`agents` não acessam banco diretamente. `policies` devem ser testáveis sem LLM.
