# SPEC-031 — PII

## Objetivo
Classificar e minimizar dados pessoais.

## Contrato / Dados
phone, email, address, CPF, name

## Regra de implementação
Logs não devem armazenar PII desnecessariamente.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
