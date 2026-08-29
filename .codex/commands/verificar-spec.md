# /verificar-spec

## Objetivo
Revisar uma implementação contra PRD, SPEC e ADRs sem alterar o código.

## Regras
- Execute em uma sessão nova.
- Leia `AGENTS.md`.
- Leia a SPEC indicada.
- Leia PRD e ADRs relacionados.
- Leia somente o diff e arquivos necessários.
- Não corrija o código.
- Não crie commit.
- Emita apenas veredito e evidências.

## Saída obrigatória

```text
VEREDITO: PASS | FAIL

SPEC analisada:
PRD relacionado:
ADRs aplicáveis:

Requisitos atendidos:
- ...

Desvios:
- ...

Riscos:
- ...

Testes ausentes:
- ...

Bloqueadores para merge:
- ...
```

## Critério
Se existir comportamento não sustentado pela SPEC, marque `FAIL`.
Se regra de segurança depender apenas de prompt quando deveria ser estrutural, marque `FAIL`.
Se uma ação irreversível não possuir checkpoint/approval quando exigido, marque `FAIL`.
