# SPEC-030 — Security

## Objetivo
Definir controles mínimos de infraestrutura.

## Contrato / Dados
IAM, Secret Manager, encryption, RBAC

## Regra de implementação
Secrets nunca no código.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
