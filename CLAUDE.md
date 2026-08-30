# CLAUDE.md — RevenueFlow AI

## Papel do Claude Code

Claude Code é um harness suportado deste repositório. O contrato de engenharia compartilhado continua em [`AGENTS.md`](AGENTS.md). Este arquivo adiciona as regras específicas de Claude Code, MCP, skills, hooks e agentes auxiliares.

## Ordem obrigatória de leitura

1. `CLAUDE.md`
2. `AGENTS.md`
3. PRD relacionado
4. SPEC relacionada
5. ADRs aplicáveis
6. testes existentes
7. código

## Invariantes

- LLM não é fonte de verdade para preço, estoque, margem, identidade, pedido ou pagamento.
- LLM interpreta; Policy Engine decide; API executa.
- Tool ausente é controle de segurança; não registrar tools proibidas.
- Ações irreversíveis exigem checkpoint/approval quando definido.
- Nunca executar pagamento real na V1.
- Nunca emitir documento fiscal real.
- Nunca remover guardrail para fazer CI passar.
- Nunca inserir segredo no repositório.
- Nunca usar credenciais de produção em teste.
- Nunca executar `terraform apply`, `terraform destroy`, exclusão de projeto, remoção de banco ou IAM destrutivo sem aprovação humana explícita no terminal.

## GCP

Plataforma principal:
- Cloud Run
- Cloud SQL PostgreSQL
- BigQuery
- Pub/Sub
- Vertex AI / Gemini
- Secret Manager
- Cloud Storage
- Artifact Registry
- IAM
- Terraform

## MCP

O MCP oficial principal deste kit é o **Google Cloud CLI remote MCP**.

Configuração de projeto:
- `.mcp.json`

Endpoint:
- `https://cloudcli.googleapis.com/mcp`

O MCP deve operar com a identidade autenticada do usuário e nunca contornar IAM.

## Skills

Skills ficam em `.claude/skills/<skill>/SKILL.md`.

Use a skill quando a tarefa corresponder ao domínio.

## Agentes auxiliares

- `gcp-architect`
- `data-engineer`
- `ai-engineer`
- `terraform-reviewer`
- `security-reviewer`
- `finops-reviewer`
- `spec-reviewer`

O `spec-reviewer` revisa e NÃO corrige código na mesma sessão.

## Hooks

Hooks em `.claude/hooks/` bloqueiam comandos destrutivos ou de alto risco.

Se um hook bloquear uma ação, não tente contorná-lo.
Explique a necessidade e peça aprovação humana.

## Rituais

- `/gcp-check`
- `/gcp-login`
- `/verify-spec`
- `/verify-risk`
- `/terraform-plan`
- `/cloud-run-check`
- `/bigquery-check`
- `/cost-check`

## Processo de feature

```text
PRD
 ↓
SPEC
 ↓
ADRs
 ↓
Implementação
 ↓
testes
 ↓
/verify-spec
 ↓
/verify-risk (quando necessário)
 ↓
PR
```

## Fluxo de contribuição / CI

- A `main` é protegida (`enforce_admins`): **sem push direto**, inclusive para admins.
- Toda tarefa de desenvolvimento cria uma branch nova (`feat/…`, `fix/…`, `chore/…`) e entra por **PR**. Merge é **squash-only**; o título do PR vira a mensagem do commit e precisa seguir Conventional Commits (`feat|fix|test|docs|refactor|chore|ci`).
- 7 checks obrigatórios e "strict" (branch atualizada): `docs`, `lint`, `typecheck`, `tests`, `security`, `pre-commit`, `pr-title`. 0 aprovações humanas exigidas — o portão é o CI.
- Portão local: `pre-commit install --install-hooks` ativa ruff, ruff-format, gitleaks, higiene de arquivos e `scripts/check_commit_msg.py` (Conventional Commits). O job `pre-commit` do CI roda os mesmos hooks.
- Comandos equivalentes ao CI: `python scripts/validate_docs.py`, `ruff check .`, `ruff format --check .`, `mypy src`, `pytest -q`, `pre-commit run --all-files`.
- Dev harness (em construção — fatia WhatsApp inbound): **Docker Compose + Makefile** (`make up/down/migrate/seed/lint/test/run`); o CI usa os mesmos comandos por trás dos alvos.
- Artefatos do fluxo SDD (`/brainstorm`, `/define`, `/design`, `/build`) ficam em `.claude/sdd/` e **não são versionados** (git-ignored).

## Catálogo documental obrigatório

Claude deve localizar e ler os documentos relacionados antes de implementar.

### PRDs
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

### SPECs
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

### ADRs
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
- [ADR-037 — Security by Architecture for Tool Permissions](docs/adrs/adr-037-security-by-architecture-for-tool-permissions.md)
- [ADR-038 — LangGraph for Stateful Agent Orchestration](docs/adrs/adr-038-langgraph-for-stateful-agent-orchestration.md)
- [ADR-039 — Persistent Interrupt Before Irreversible Actions](docs/adrs/adr-039-persistent-interrupt-before-irreversible-actions.md)
- [ADR-040 — Observability From First Functional Slice](docs/adrs/adr-040-observability-from-first-functional-slice.md)
- [ADR-041 — Independent Spec Verification Ritual](docs/adrs/adr-041-independent-spec-verification-ritual.md)
- [ADR-042 — Google Cloud CLI Remote MCP for Developer Harness](docs/adrs/adr-042-google-cloud-cli-remote-mcp-for-developer-harness.md)
- [ADR-043 — Claude Code Hooks Block Destructive GCP Actions](docs/adrs/adr-043-claude-code-hooks-block-destructive-gcp-actions.md)
- [ADR-044 — Pub/Sub para processamento assíncrono do webhook, atrás de uma porta EventPublisher](docs/adrs/adr-044-pub-sub-async-webhook-with-publisher-port.md)
- [ADR-045 — Langfuse self-hosted atrás de uma porta Tracer](docs/adrs/adr-045-langfuse-self-hosted-behind-tracer-port.md)
- [ADR-046 — Docker Compose e Makefile como harness de desenvolvimento](docs/adrs/adr-046-docker-compose-and-makefile-dev-harness.md)
