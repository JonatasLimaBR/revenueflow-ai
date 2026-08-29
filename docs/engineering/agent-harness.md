# Agent Harness — Codex

## Escolha
O harness principal é **Codex**.

## Por quê
O projeto exige trabalho orientado ao repositório, leitura de contexto local, implementação incremental, execução de testes e mudanças auditáveis. `AGENTS.md` funciona como contrato operacional para o agente.

## Fluxo
```text
PRD → SPEC → ADR constraints → Codex → Code + Tests → CI → Pull Request → Human Review → main
```

## Precedência
1. Segurança
2. `AGENTS.md`
3. ADRs aceitos
4. SPECs
5. PRDs
6. Código atual
7. Sugestão do agente

## Automatizado para o agente
- validação documental;
- lint/format;
- type check;
- unit/integration tests;
- AI evals;
- security tests;
- criação de mocks;
- coverage;
- descrição de PR.

## Deliberadamente fora da autonomia
- merge na main;
- regra financeira;
- credenciais;
- pagamento produtivo;
- outbound fora do Policy Gate;
- remoção de guardrails;
- mudança arquitetural sem ADR;
- promoção para produção sem revisão.

## Estratégia de implementação
```text
1. Domain model
2. Repository interface
3. Service
4. Tool
5. Agent integration
6. Unit tests
7. Integration tests
8. AI eval
9. Observability
10. Docs
```


## Rituais versionados

- `/verificar-spec` — revisão independente de aderência à SPEC.
- `/verificar-risco` — revisão independente de riscos e permissões.

O revisor não corrige a implementação na mesma sessão.
