# RevenueFlow AI — Documentação de Produto e Arquitetura

Estrutura pensada para uso direto em GitHub, Cursor, Claude Code ou Codex.

## PRDs
- [PRD-001 — Visão e Objetivos do Produto](docs/prd/prd-001-vis-o-e-objetivos-do-produto.md)
- [PRD-002 — Novo Cliente via WhatsApp](docs/prd/prd-002-novo-cliente-via-whatsapp.md)
- [PRD-003 — Cliente Existente e Customer 360](docs/prd/prd-003-cliente-existente-e-customer-360.md)
- [PRD-004 — Catálogo e Recomendação de Produtos](docs/prd/prd-004-cat-logo-e-recomenda-o-de-produtos.md)
- [PRD-005 — Preço, Margem e Negociação](docs/prd/prd-005-pre-o-margem-e-negocia-o.md)
- [PRD-006 — Estoque e Prazo](docs/prd/prd-006-estoque-e-prazo.md)
- [PRD-007 — Propostas Comerciais](docs/prd/prd-007-propostas-comerciais.md)
- [PRD-008 — Pedidos e Confirmação](docs/prd/prd-008-pedidos-e-confirma-o.md)
- [PRD-009 — Human-in-the-Loop](docs/prd/prd-009-human-in-the-loop.md)
- [PRD-010 — Opportunity Engine](docs/prd/prd-010-opportunity-engine.md)
- [PRD-011 — Venda Ativa via WhatsApp](docs/prd/prd-011-venda-ativa-via-whatsapp.md)
- [PRD-012 — Arquitetura Multiagente](docs/prd/prd-012-arquitetura-multiagente.md)
- [PRD-013 — Observabilidade, Auditoria e Custos de IA](docs/prd/prd-013-observabilidade-auditoria-e-custos-de-ia.md)
- [PRD-014 — Segurança e Privacidade](docs/prd/prd-014-seguran-a-e-privacidade.md)
- [PRD-015 — Analytics e Revenue Intelligence](docs/prd/prd-015-analytics-e-revenue-intelligence.md)
- [PRD-016 — Escopo e Critérios da V1](docs/prd/prd-016-escopo-e-crit-rios-da-v1.md)

## SPECs
- [SPEC-001 — WhatsApp Webhook](docs/specs/spec-001-whatsapp-webhook.md)
- [SPEC-002 — Conversation Session](docs/specs/spec-002-conversation-session.md)
- [SPEC-003 — Identificação do Cliente](docs/specs/spec-003-identifica-o-do-cliente.md)
- [SPEC-004 — Lead Creation](docs/specs/spec-004-lead-creation.md)
- [SPEC-005 — Intent Classification](docs/specs/spec-005-intent-classification.md)
- [SPEC-006 — Product Search](docs/specs/spec-006-product-search.md)
- [SPEC-007 — Product Recommendation](docs/specs/spec-007-product-recommendation.md)
- [SPEC-008 — Inventory Service](docs/specs/spec-008-inventory-service.md)
- [SPEC-009 — Pricing Service](docs/specs/spec-009-pricing-service.md)
- [SPEC-010 — Pricing Guardrail](docs/specs/spec-010-pricing-guardrail.md)
- [SPEC-011 — Negotiation Agent](docs/specs/spec-011-negotiation-agent.md)
- [SPEC-012 — Human Approval](docs/specs/spec-012-human-approval.md)
- [SPEC-013 — Quote](docs/specs/spec-013-quote.md)
- [SPEC-014 — Confirmation](docs/specs/spec-014-confirmation.md)
- [SPEC-015 — Order](docs/specs/spec-015-order.md)
- [SPEC-016 — Payment Sandbox](docs/specs/spec-016-payment-sandbox.md)
- [SPEC-017 — Customer 360](docs/specs/spec-017-customer-360.md)
- [SPEC-018 — Opportunity Engine](docs/specs/spec-018-opportunity-engine.md)
- [SPEC-019 — Replenishment Rule](docs/specs/spec-019-replenishment-rule.md)
- [SPEC-020 — Quote Recovery](docs/specs/spec-020-quote-recovery.md)
- [SPEC-021 — Opportunity Entity](docs/specs/spec-021-opportunity-entity.md)
- [SPEC-022 — Outbound Contact](docs/specs/spec-022-outbound-contact.md)
- [SPEC-023 — Agent Supervisor](docs/specs/spec-023-agent-supervisor.md)
- [SPEC-024 — Allowed Agents](docs/specs/spec-024-allowed-agents.md)
- [SPEC-025 — Tool Permissions](docs/specs/spec-025-tool-permissions.md)
- [SPEC-026 — Human Handoff](docs/specs/spec-026-human-handoff.md)
- [SPEC-027 — Handoff Context](docs/specs/spec-027-handoff-context.md)
- [SPEC-028 — Audit Trail](docs/specs/spec-028-audit-trail.md)
- [SPEC-029 — Grounding](docs/specs/spec-029-grounding.md)
- [SPEC-030 — Security](docs/specs/spec-030-security.md)
- [SPEC-031 — PII](docs/specs/spec-031-pii.md)
- [SPEC-032 — Prompt Injection](docs/specs/spec-032-prompt-injection.md)
- [SPEC-033 — Idempotency](docs/specs/spec-033-idempotency.md)
- [SPEC-034 — Observability](docs/specs/spec-034-observability.md)
- [SPEC-035 — Performance](docs/specs/spec-035-performance.md)
- [SPEC-036 — Testing](docs/specs/spec-036-testing.md)
- [SPEC-037 — Technology Stack](docs/specs/spec-037-technology-stack.md)

## ADRs
- [ADR-001 — GCP como cloud principal](docs/adrs/adr-001-gcp-como-cloud-principal.md)
- [ADR-002 — Cloud Run como runtime](docs/adrs/adr-002-cloud-run-como-runtime.md)
- [ADR-003 — Monólito modular na V1](docs/adrs/adr-003-mon-lito-modular-na-v1.md)
- [ADR-004 — PostgreSQL como OLTP](docs/adrs/adr-004-postgresql-como-oltp.md)
- [ADR-005 — BigQuery como analytics](docs/adrs/adr-005-bigquery-como-analytics.md)
- [ADR-006 — Pub/Sub como event backbone](docs/adrs/adr-006-pub-sub-como-event-backbone.md)
- [ADR-007 — Arquitetura multiagente](docs/adrs/adr-007-arquitetura-multiagente.md)
- [ADR-008 — Least privilege para agentes](docs/adrs/adr-008-least-privilege-para-agentes.md)
- [ADR-009 — LLM não é System of Record](docs/adrs/adr-009-llm-n-o-system-of-record.md)
- [ADR-010 — RAG apenas para conteúdo não estruturado](docs/adrs/adr-010-rag-apenas-para-conte-do-n-o-estruturado.md)
- [ADR-011 — Pricing determinístico](docs/adrs/adr-011-pricing-determin-stico.md)
- [ADR-012 — Negotiation Agent limitado](docs/adrs/adr-012-negotiation-agent-limitado.md)
- [ADR-013 — Human-in-the-Loop](docs/adrs/adr-013-human-in-the-loop.md)
- [ADR-014 — Separar AI Decision de Business Decision](docs/adrs/adr-014-separar-ai-decision-de-business-decision.md)
- [ADR-015 — WhatsApp como primeiro canal](docs/adrs/adr-015-whatsapp-como-primeiro-canal.md)
- [ADR-016 — Core independente do WhatsApp](docs/adrs/adr-016-core-independente-do-whatsapp.md)
- [ADR-017 — Lead scoring por regras](docs/adrs/adr-017-lead-scoring-por-regras.md)
- [ADR-018 — ML após histórico suficiente](docs/adrs/adr-018-ml-ap-s-hist-rico-suficiente.md)
- [ADR-019 — Opportunity Engine separado do Sales Agent](docs/adrs/adr-019-opportunity-engine-separado-do-sales-agent.md)
- [ADR-020 — Outbound exige Policy Gate](docs/adrs/adr-020-outbound-exige-policy-gate.md)
- [ADR-021 — Idempotência obrigatória](docs/adrs/adr-021-idempot-ncia-obrigat-ria.md)
- [ADR-022 — Observabilidade completa dos agentes](docs/adrs/adr-022-observabilidade-completa-dos-agentes.md)
- [ADR-023 — AI Cost como KPI de negócio](docs/adrs/adr-023-ai-cost-como-kpi-de-neg-cio.md)
- [ADR-024 — Prompt injection não altera regras](docs/adrs/adr-024-prompt-injection-n-o-altera-regras.md)
- [ADR-025 — Tools financeiras determinísticas](docs/adrs/adr-025-tools-financeiras-determin-sticas.md)
- [ADR-026 — Databricks Free fora do caminho crítico](docs/adrs/adr-026-databricks-free-fora-do-caminho-cr-tico.md)
- [ADR-027 — GCP como System of Record](docs/adrs/adr-027-gcp-como-system-of-record.md)
- [ADR-028 — Dados simulados primeiro](docs/adrs/adr-028-dados-simulados-primeiro.md)
- [ADR-029 — Pagamento somente sandbox](docs/adrs/adr-029-pagamento-somente-sandbox.md)
- [ADR-030 — Documento comercial simulado](docs/adrs/adr-030-documento-comercial-simulado.md)
- [ADR-031 — Security by Design](docs/adrs/adr-031-security-by-design.md)
- [ADR-032 — PII minimization](docs/adrs/adr-032-pii-minimization.md)
- [ADR-033 — Customer 360 não vai inteiro ao LLM](docs/adrs/adr-033-customer-360-n-o-vai-inteiro-ao-llm.md)
- [ADR-034 — Explicabilidade comercial](docs/adrs/adr-034-explicabilidade-comercial.md)
- [ADR-035 — Receita como principal métrica](docs/adrs/adr-035-receita-como-principal-m-trica.md)
- [ADR-036 — Autonomia proporcional ao risco](docs/adrs/adr-036-autonomia-proporcional-ao-risco.md)

## Estrutura

```text
revenueflow-ai-docs/
├── README.md
└── docs/
    ├── prd/
    │   ├── PRD-001 ...
    │   └── PRD-016 ...
    ├── specs/
    │   ├── SPEC-001 ...
    │   └── SPEC-037 ...
    └── adrs/
        ├── ADR-001 ...
        └── ADR-036 ...
```

## Convenção
Cada decisão, especificação e requisito de produto possui um arquivo independente para facilitar:
- revisão por Pull Request;
- histórico Git;
- linking entre documentos;
- implementação por agentes de código;
- rastreabilidade entre produto, arquitetura, testes e código.

## Agent Harness e Processo de Engenharia

O harness oficial é **Codex**, dirigido por [`AGENTS.md`](AGENTS.md).

Documentação adicional:
- [Agent Harness](docs/engineering/agent-harness.md)
- [Estrutura do Repositório](docs/engineering/repository-structure.md)
- [Processo Visível](docs/engineering/visible-process.md)
- [Política de Revisão](docs/engineering/review-policy.md)
- [Contributing](CONTRIBUTING.md)

A `main` deve ser protegida, mudanças entram por Pull Request e o workflow de CI valida documentação, lint, tipos, testes e secrets.

### Controles agentic adicionais
- [Arquitetura Agentic](docs/engineering/agentic-architecture.md)
- [Matriz de Permissões de Tools](docs/engineering/tool-permission-matrix.md)
- [Ritual `/verificar-spec`](.codex/commands/verificar-spec.md)
- [Ritual `/verificar-risco`](.codex/commands/verificar-risco.md)

## GCP + Claude Code Dev Kit

Este repositório inclui um harness Claude Code completo para GCP:

- [`CLAUDE.md`](CLAUDE.md)
- [Guia do Dev Kit](GCP_CLAUDE_CODE_DEV_KIT.md)
- `.mcp.json`
- `.claude/skills/`
- `.claude/agents/`
- `.claude/commands/`
- `.claude/hooks/`

O MCP principal é o Google Cloud CLI remote MCP. Ações destrutivas são bloqueadas por hook e continuam sujeitas a IAM e aprovação humana.
