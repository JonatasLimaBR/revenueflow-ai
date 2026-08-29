# Contributing

## Fluxo
1. Selecione PRD/SPEC.
2. Abra branch curta.
3. Implemente com testes.
4. Rode checks.
5. Abra PR.
6. Resolva comentários.
7. Aguarde aprovação.
8. Faça merge somente com CI verde.

## Checks
```bash
python scripts/validate_docs.py
ruff check .
ruff format --check .
mypy src
pytest -q
```

## Segurança
Nunca commitar `.env`, tokens, service account JSON, chaves privadas ou credenciais de WhatsApp.
