# Processo Visível

## Branches
`main` deve ser protegida.

Padrões:
- `feat/<descricao>`
- `fix/<descricao>`
- `docs/<descricao>`
- `refactor/<descricao>`
- `test/<descricao>`
- `chore/<descricao>`

## Pull Requests
Nenhuma mudança entra diretamente na `main`.

Todo PR deve referenciar PRD, SPEC e ADR aplicável.

## Commits
Usar Conventional Commits.

Evitar commits como `update`, `ajustes`, `final`, `fix2`.

## Checks required
1. docs
2. lint
3. typecheck
4. tests
5. security

## Proteção sugerida para main no GitHub
- Require pull request before merging
- Require at least 1 approval
- Dismiss stale approvals
- Require status checks
- Require conversation resolution
- Require linear history
- Block force pushes
- Block deletion

## Mudança arquitetural
```text
New ADR → Review → Accepted → Implementation
```

## Mudança de regra crítica
Pricing, margem, approval e outbound exigem:
- teste unitário;
- teste negativo;
- referência no PR;
- revisão humana.
