# RevenueFlow AI — GCP Claude Code Dev Kit

## Objetivo

Preparar o repositório para desenvolvimento profissional com Claude Code em GCP usando:

- `CLAUDE.md`;
- MCP;
- skills;
- subagents;
- slash commands;
- hooks;
- autenticação GCP;
- Terraform guardrails;
- revisão independente;
- PRD/SPEC/ADR como fonte de engenharia.

## Estrutura

```text
CLAUDE.md
.mcp.json
.claude/
├── settings.json
├── hooks/
│   └── pre_bash_guard.py
├── commands/
├── agents/
└── skills/
mcp/
scripts/
```

## 1. Pré-requisitos

- Git
- Python 3.12+
- Google Cloud CLI
- Claude Code
- conta/projeto GCP autorizado

## 2. Instalação no Windows PowerShell

Na raiz do repositório:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-gcp-claude-kit.ps1
```

O script:
- verifica `gcloud`;
- verifica `claude`;
- abre autenticação Google;
- opcionalmente configura ADC;
- define o projeto GCP.

Ele NÃO:
- habilita APIs;
- cria IAM;
- cria chaves;
- executa Terraform;
- faz deploy.

## 3. Linux/macOS

```bash
./scripts/install-gcp-claude-kit.sh
```

## 4. Autenticação manual

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project PROJECT_ID
gcloud auth list
gcloud config get-value project
```

Use ADC apenas quando SDKs locais precisarem.

Em workloads no GCP, prefira identidades anexadas/Workload Identity a arquivos de chave.

## 5. MCP

O `.mcp.json` do projeto registra:

```text
gcp-cli
https://cloudcli.googleapis.com/mcp
```

O servidor remoto usa IAM/credenciais Google para autorizar operações.

### Importante

O Cloud CLI remote MCP é recurso Preview/Pre-GA. Não torne a aplicação RevenueFlow dependente dele em runtime. Ele é ferramenta de desenvolvimento/operabilidade do harness.

## 6. Skills incluídas

- `gcp-auth`
- `cloud-run`
- `bigquery`
- `cloud-sql`
- `pubsub`
- `vertex-ai`
- `terraform-gcp`
- `gcp-security`
- `finops`
- `revenueflow-architecture`

## 7. Subagents

- GCP Architect
- Data Engineer
- AI Engineer
- Terraform Reviewer
- Security Reviewer
- FinOps Reviewer
- Spec Reviewer

Revisores são read-only por regra.

## 8. Commands

```text
/gcp-login
/gcp-check
/verify-spec
/verify-risk
/terraform-plan
/cloud-run-check
/bigquery-check
/cost-check
```

## 9. Hook de proteção

`.claude/hooks/pre_bash_guard.py` bloqueia automaticamente padrões de alto risco, incluindo:

- `terraform apply`;
- `terraform destroy`;
- exclusão de projeto;
- exclusão de Cloud SQL;
- exclusão de Cloud Run;
- remoções recursivas de storage;
- exclusão de service accounts;
- remoções IAM críticas.

O objetivo não é substituir IAM. É criar uma barreira adicional no harness.

## 10. PRD / SPEC / ADR

`CLAUDE.md` possui catálogo completo de todos os PRDs, SPECs e ADRs.

A ordem de trabalho é:

```text
PRD → SPEC → ADRs → code → tests → /verify-spec → PR
```

## 11. Segurança por arquitetura

Se Recommendation Agent não pode criar pedido, ele não recebe `create_order`.

Não use:
> "Você possui create_order, mas nunca use."

Use:
> A tool não é registrada para esse agente.

## 12. Terraform

Claude pode automaticamente:

```bash
terraform fmt
terraform validate
terraform plan
```

Não pode automaticamente:

```bash
terraform apply
terraform destroy
```

## 13. Primeiro uso

Após autenticação:

```bash
claude
```

Então:

```text
/gcp-check
```

Depois peça ao Claude:

```text
Leia CLAUDE.md, AGENTS.md, PRD-002, SPEC-001 e os ADRs relacionados.
Não implemente ainda. Produza o plano técnico para o WhatsApp webhook.
```

## 14. Processo de revisão

Depois da implementação:

```text
/verify-spec
/verify-risk
```

Idealmente em uma sessão nova.

O revisor não deve corrigir código, apenas emitir veredito.
