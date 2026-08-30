# Contributing

## Fluxo
1. Selecione PRD/SPEC.
2. Abra branch curta a partir da `main`.
3. Implemente com testes.
4. Rode os checks locais (ou deixe o pre-commit rodar).
5. Abra PR com título no padrão Conventional Commits (vira a mensagem do squash).
6. Resolva os comentários (conversas precisam estar resolvidas).
7. Faça merge quando o CI ficar verde.

Não há aprovação humana obrigatória: num time de uma pessoa, aprovar o próprio
PR é teatro. O portão é o CI, não a revisão. A `main` é protegida e as regras
valem inclusive para administradores — não há botão de bypass.

## Portão local (pre-commit)
Instale uma vez por clone:

```bash
pip install pre-commit
pre-commit install --install-hooks
```

Isso ativa, a cada commit: `ruff` (lint + fix), `ruff-format`, `gitleaks`
(segredos), higiene de arquivos, e a validação da mensagem de commit
(Conventional Commits). Rodar em tudo manualmente: `pre-commit run --all-files`.

## Checks (equivalentes ao CI)
```bash
python scripts/validate_docs.py
ruff check .
ruff format --check .
mypy src
pytest -q
pre-commit run --all-files
```

Ou, com o harness Docker (ADR-046): `make check` roda tudo; `make up` sobe a
stack local (`postgres`, emulador do Pub/Sub, Langfuse, `app`).

## Trabalho paralelo (múltiplos agentes)
O desenvolvimento pode envolver vários agentes trabalhando ao mesmo tempo. Para
não colidirem:

- **Uma branch e um PR por tarefa**, com escopo de arquivos disjunto entre PRs
  abertos simultaneamente.
- Branches curtas: rebase na `main` antes do merge (os checks `strict` já exigem
  a branch atualizada).
- O corpo do PR referencia a PRD/SPEC/ADR que implementa.
- Um arquivo é editado por um PR de cada vez; se dois precisam do mesmo arquivo,
  serializam.
- Cada PR é verificável e mergeável de forma independente (`ruff` + `mypy` +
  `pytest` verdes localmente antes de abrir).

## Commits e título de PR
Conventional Commits, tipos: `feat`, `fix`, `test`, `docs`, `refactor`,
`chore`, `ci`. O merge é **squash-only**; o título do PR precisa seguir o
padrão porque ele se torna a mensagem do commit na `main`.

## Segurança
Nunca commitar `.env`, tokens, service account JSON, chaves privadas ou
credenciais de WhatsApp. O `gitleaks` roda local (pre-commit) e no CI.
